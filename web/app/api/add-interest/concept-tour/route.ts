import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient } from "@/lib/surveyState";

// Records one concept-tour submission. Called per resolved interest during
// onboarding Stage 5 (survey-and-difficulty-design.md §1.6). Idempotent for
// re-runs of the same tour — comfort_responses_json is a merged map keyed by
// "<node_slug>:<subtopic_key>".

interface AddressedTile {
  node_id: string;
  node_slug: string;
  subtopic_key: string;
  state: "familiar" | "refresh" | "new";
}

interface Body {
  addressed: AddressedTile[];
  // Loose label for which interest this tour belonged to, for the
  // operator-visible comfort_responses_json (not strictly required).
  for_interest_node_slug?: string;
}

// state precedence for the foundation-node-level user_node_states row.
// concept tour signals never DOWNGRADE comfort.
function bumpedState(
  current: string | null | undefined,
  signal: "familiar" | "refresh" | "new",
): string | null {
  if (current === "struggling") return null; // never override struggling
  if (signal === "familiar") {
    if (current === "comfortable") return null; // no-op
    return "comfortable";
  }
  if (signal === "refresh") {
    if (current === "comfortable" || current === "active") return null;
    return "active"; // bump from unseen → active
  }
  return null; // 'new' is the default, no change to make
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const addressed = (body.addressed ?? []).filter(
    (t) =>
      t &&
      typeof t.node_id === "string" &&
      typeof t.subtopic_key === "string" &&
      ["familiar", "refresh", "new"].includes(t.state),
  );

  try {
    const admin = getAdminClient();

    // 1) Append to surveys.comfort_responses_json (merged map).
    const { data: surveyRow } = await admin
      .from("surveys")
      .select("comfort_responses_json")
      .eq("user_id", user.id)
      .maybeSingle();

    const existing =
      (surveyRow?.comfort_responses_json as
        | { subtopics?: Record<string, string> }
        | undefined) ?? {};
    const subtopics = { ...(existing.subtopics ?? {}) };
    for (const t of addressed) {
      subtopics[`${t.node_slug}:${t.subtopic_key}`] = t.state;
    }
    await admin
      .from("surveys")
      .update({
        comfort_responses_json: { subtopics },
        updated_at: new Date().toISOString(),
      })
      .eq("user_id", user.id);

    // 2) Bump user_node_states for the foundation nodes the addressed
    //    subtopics belong to. We pick the strongest signal per foundation
    //    and never downgrade existing comfort.
    const byNodeId = new Map<string, AddressedTile[]>();
    for (const t of addressed) {
      const list = byNodeId.get(t.node_id) ?? [];
      list.push(t);
      byNodeId.set(t.node_id, list);
    }

    if (byNodeId.size > 0) {
      const nodeIds = Array.from(byNodeId.keys());
      const { data: stateRows } = await admin
        .from("user_node_states")
        .select("node_id, state")
        .eq("user_id", user.id)
        .in("node_id", nodeIds);

      const currentByNode = new Map<string, string>();
      for (const r of stateRows ?? []) {
        currentByNode.set(r.node_id as string, r.state as string);
      }

      const upserts: Array<{ user_id: string; node_id: string; state: string }> = [];
      for (const [nodeId, tiles] of byNodeId) {
        // strongest signal per node: familiar > refresh > new
        const hasFamiliar = tiles.some((t) => t.state === "familiar");
        const hasRefresh = tiles.some((t) => t.state === "refresh");
        const signal = hasFamiliar ? "familiar" : hasRefresh ? "refresh" : "new";
        const next = bumpedState(currentByNode.get(nodeId), signal);
        if (next) {
          upserts.push({ user_id: user.id, node_id: nodeId, state: next });
        }
      }

      if (upserts.length > 0) {
        const { error } = await admin
          .from("user_node_states")
          .upsert(upserts, { onConflict: "user_id,node_id" });
        if (error) console.error("user_node_states upsert failed:", error);
      }
    }

    // 3) Write per-subtopic rows to user_subtopic_states (Step 6, §7). This is
    //    the durable per-subtopic store the skill tree node panel reads. We
    //    write every addressed tile, including 'new', so re-running the tour
    //    can downgrade a stale 'familiar' to 'refresh' if the user changes
    //    their mind.
    const subtopicRows = addressed.map((t) => ({
      user_id: user.id,
      node_id: t.node_id,
      subtopic_slug: t.subtopic_key,
      state: t.state,
      updated_at: new Date().toISOString(),
    }));
    if (subtopicRows.length > 0) {
      const { error } = await admin
        .from("user_subtopic_states")
        .upsert(subtopicRows, { onConflict: "user_id,node_id,subtopic_slug" });
      if (error) console.error("user_subtopic_states upsert failed:", error);
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
