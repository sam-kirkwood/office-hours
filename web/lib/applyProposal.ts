import type { SupabaseClient } from "@supabase/supabase-js";

function nodeIdsFromPayload(kind: string, payload: Record<string, unknown>): string[] {
  switch (kind) {
    case "merge":
      return [payload.source_node_id, payload.target_node_id].filter(Boolean) as string[];
    case "split":
      return [payload.source_node_id].filter(Boolean) as string[];
    case "rename":
    case "promote":
    case "demote":
    case "deprecate":
      return [payload.node_id].filter(Boolean) as string[];
    case "add_edge":
      return [payload.source_node_id, payload.target_node_id].filter(Boolean) as string[];
    default:
      return [];
  }
}

export async function validateNodeIds(
  supabase: SupabaseClient,
  kind: string,
  payload: Record<string, unknown>,
): Promise<{ valid: boolean; missingIds: string[] }> {
  const ids = nodeIdsFromPayload(kind, payload);
  if (ids.length === 0) return { valid: true, missingIds: [] };

  const { data } = await supabase.from("nodes").select("id").in("id", ids);

  const found = new Set((data ?? []).map((r: { id: string }) => r.id));
  const missingIds = ids.filter((id) => !found.has(id));
  return { valid: missingIds.length === 0, missingIds };
}

export async function applyMerge(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  const source = payload.source_node_id as string;
  const target = payload.target_node_id as string;

  // Repoint edges both directions
  await supabase.from("edges").update({ source_node_id: target }).eq("source_node_id", source);
  await supabase.from("edges").update({ target_node_id: target }).eq("target_node_id", source);

  // Dedup edges: after repointing, find duplicate (src, tgt, kind) groups and keep highest weight
  const { data: allEdges } = await supabase
    .from("edges")
    .select("id, source_node_id, target_node_id, edge_kind, weight")
    .or(`source_node_id.eq.${target},target_node_id.eq.${target}`);

  const edgeMap = new Map<string, { id: string; weight: number }[]>();
  for (const edge of allEdges ?? []) {
    const key = `${edge.source_node_id}:${edge.target_node_id}:${edge.edge_kind}`;
    if (!edgeMap.has(key)) edgeMap.set(key, []);
    edgeMap.get(key)!.push({ id: edge.id, weight: edge.weight ?? 0 });
  }
  for (const group of edgeMap.values()) {
    if (group.length <= 1) continue;
    group.sort((a, b) => b.weight - a.weight);
    const toDelete = group.slice(1).map((e) => e.id);
    await supabase.from("edges").delete().in("id", toDelete);
  }

  // user_interests: users with source-only → repoint; users with both → delete source
  const { data: sourceInterests } = await supabase
    .from("user_interests")
    .select("user_id")
    .eq("node_id", source);

  for (const row of sourceInterests ?? []) {
    const { data: hasTarget } = await supabase
      .from("user_interests")
      .select("user_id")
      .eq("user_id", row.user_id)
      .eq("node_id", target)
      .maybeSingle();

    if (hasTarget) {
      await supabase
        .from("user_interests")
        .delete()
        .eq("user_id", row.user_id)
        .eq("node_id", source);
    } else {
      await supabase
        .from("user_interests")
        .update({ node_id: target })
        .eq("user_id", row.user_id)
        .eq("node_id", source);
    }
  }

  // user_node_states: same pattern
  const { data: sourceStates } = await supabase
    .from("user_node_states")
    .select("user_id")
    .eq("node_id", source);

  for (const row of sourceStates ?? []) {
    const { data: hasTarget } = await supabase
      .from("user_node_states")
      .select("user_id")
      .eq("user_id", row.user_id)
      .eq("node_id", target)
      .maybeSingle();

    if (hasTarget) {
      await supabase
        .from("user_node_states")
        .delete()
        .eq("user_id", row.user_id)
        .eq("node_id", source);
    } else {
      await supabase
        .from("user_node_states")
        .update({ node_id: target })
        .eq("user_id", row.user_id)
        .eq("node_id", source);
    }
  }

  // queue_items: repoint concept_review and suggested_interest refs
  await supabase
    .from("queue_items")
    .update({ ref_id: target })
    .eq("ref_id", source)
    .in("kind", ["concept_review", "suggested_interest"]);

  // problems: repoint topic_node_id
  await supabase.from("problems").update({ topic_node_id: target }).eq("topic_node_id", source);

  // Deprecate source node
  await supabase
    .from("nodes")
    .update({ pool_status: "deprecated", updated_at: new Date().toISOString() })
    .eq("id", source);
}

export async function applySplit(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  await supabase.from("nodes").insert({
    slug: payload.new_node_slug,
    title: payload.new_node_title,
    description_md: payload.new_node_description_md ?? null,
    domain: payload.new_node_domain,
    kind: "interest",
    difficulty_hint: payload.new_node_difficulty_hint ?? null,
    pool_status: "active",
  });
  // User associations stay on the source node — add edges via megagraph view if needed
  console.log("Split simplified — user state remains on source node:", payload.source_node_id);
}

export async function applyRename(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  const nodeId = payload.node_id as string;
  const newTitle = payload.new_title as string;
  const newSlug = payload.new_slug as string;

  const { data: node } = await supabase
    .from("nodes")
    .select("slug")
    .eq("id", nodeId)
    .single();

  const oldSlug = node?.slug as string | undefined;

  await supabase
    .from("nodes")
    .update({ title: newTitle, slug: newSlug, updated_at: new Date().toISOString() })
    .eq("id", nodeId);

  if (oldSlug && oldSlug !== newSlug) {
    const { data: entries } = await supabase
      .from("notebook_entries")
      .select("id, topic_node_slugs")
      .filter("topic_node_slugs", "cs", JSON.stringify([oldSlug]));

    if ((entries?.length ?? 0) > 50) {
      console.warn(
        `Rename of "${oldSlug}" → "${newSlug}" affected ${entries!.length} notebook entries — verify for slug duplicates.`,
      );
    }

    for (const entry of entries ?? []) {
      const updated = (entry.topic_node_slugs as string[]).map((s: string) =>
        s === oldSlug ? newSlug : s,
      );
      await supabase
        .from("notebook_entries")
        .update({ topic_node_slugs: updated })
        .eq("id", entry.id);
    }
  }
}

export async function applyPromote(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  await supabase
    .from("nodes")
    .update({ kind: "foundation", updated_at: new Date().toISOString() })
    .eq("id", payload.node_id);
}

export async function applyDemote(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  await supabase
    .from("nodes")
    .update({ kind: "interest", updated_at: new Date().toISOString() })
    .eq("id", payload.node_id);
}

export async function applyAddEdge(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  const { data: existing } = await supabase
    .from("edges")
    .select("id")
    .eq("source_node_id", payload.source_node_id)
    .eq("target_node_id", payload.target_node_id)
    .eq("edge_kind", payload.edge_kind)
    .maybeSingle();

  if (existing) {
    await supabase.from("edges").update({ weight: payload.weight }).eq("id", existing.id);
  } else {
    await supabase.from("edges").insert({
      source_node_id: payload.source_node_id,
      target_node_id: payload.target_node_id,
      edge_kind: payload.edge_kind,
      weight: payload.weight,
    });
  }
}

export async function applyDeprecate(
  supabase: SupabaseClient,
  payload: Record<string, unknown>,
): Promise<void> {
  await supabase
    .from("nodes")
    .update({ pool_status: "deprecated", updated_at: new Date().toISOString() })
    .eq("id", payload.node_id);

  await supabase
    .from("queue_items")
    .update({ state: "dismissed" })
    .eq("ref_id", payload.node_id)
    .in("kind", ["concept_review", "suggested_interest"]);
}
