// Server-side helper shared by the GET /api/queue route and the daily server
// component. Avoids an intra-process HTTP round-trip.

import type { SupabaseClient } from "@supabase/supabase-js";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { surfaceDaily, maybeRefillQueue } from "@/lib/pythonApi";
import type { QueueResult, SurfacedQueueItem } from "@/lib/types";

export type { QueueResult };

function is404(err: unknown): boolean {
  return err instanceof Error && err.message.includes("404");
}

export function toItem(raw: {
  id?: string;
  queue_item_id?: string;
  kind: string;
  ref_id: string | null;
  added_reason: string | null;
  time_estimate_minutes_low: number | null;
  time_estimate_minutes_high: number | null;
  via_refresher?: boolean;
}): SurfacedQueueItem {
  return {
    queue_item_id: (raw.id ?? raw.queue_item_id)!,
    kind: raw.kind,
    ref_id: raw.ref_id,
    added_reason: raw.added_reason,
    time_estimate_minutes_low: raw.time_estimate_minutes_low,
    time_estimate_minutes_high: raw.time_estimate_minutes_high,
    via_refresher: raw.via_refresher ?? false,
  };
}


export async function resolveTitles(items: SurfacedQueueItem[]): Promise<SurfacedQueueItem[]> {
  const idsForKind = (kind: string) =>
    items.filter((i) => i.kind === kind && i.ref_id).map((i) => i.ref_id as string);

  const problemIds = idsForKind("problem");
  const engagementIds = idsForKind("paper_engagement");
  const conceptNodeIds = idsForKind("concept_review");
  // A suggested_interest's ref_id IS a node — it's both the (unset) title and
  // the topic chip.
  const suggestedNodeIds = idsForKind("suggested_interest");

  if (
    problemIds.length === 0 &&
    engagementIds.length === 0 &&
    conceptNodeIds.length === 0 &&
    suggestedNodeIds.length === 0
  ) {
    return items;
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const titleByRefId: Record<string, string> = {};
  // d22: the topic/interest node(s) each item is drawn from, shown as chips.
  const topicsByRefId: Record<string, string[]> = {};
  const inProgressByRefId: Record<string, boolean> = {};

  // Node ids whose titles we need, across all kinds — resolved in one fetch.
  const neededNodeIds = new Set<string>([...conceptNodeIds, ...suggestedNodeIds]);

  // --- problems: title + topic node id -------------------------------------
  let problemRows: Array<{ id: string; title: string | null; topic_node_id: string | null }> = [];
  if (problemIds.length > 0) {
    const { data } = await adminClient
      .from("problems")
      .select("id, title, topic_node_id")
      .in("id", problemIds);
    problemRows = (data ?? []) as typeof problemRows;
    for (const p of problemRows) if (p.topic_node_id) neededNodeIds.add(p.topic_node_id);
  }

  // --- paper engagements: title (paper) + topic node ids (paper) ------------
  let engagements: Array<{
    id: string;
    paper_id: string | null;
    state: string | null;
    current_question_index: number | null;
  }> = [];
  let paperById: Record<string, { title: string | null; topic_node_ids: string[] }> = {};
  if (engagementIds.length > 0) {
    const { data } = await adminClient
      .from("paper_engagements")
      .select("id, paper_id, state, current_question_index")
      .in("id", engagementIds);
    engagements = (data ?? []) as typeof engagements;

    for (const e of engagements) {
      const started = e.state === "in_progress" || (e.current_question_index ?? 0) > 0;
      if (started) inProgressByRefId[e.id] = true;
    }

    const paperIds = engagements.map((e) => e.paper_id).filter((x): x is string => Boolean(x));
    if (paperIds.length > 0) {
      const { data: papers } = await adminClient
        .from("papers")
        .select("id, title, topic_node_ids")
        .in("id", paperIds);
      paperById = Object.fromEntries(
        (papers ?? []).map((p: { id: string; title: string | null; topic_node_ids: string[] | null }) => [
          p.id,
          { title: p.title, topic_node_ids: p.topic_node_ids ?? [] },
        ]),
      );
      for (const p of Object.values(paperById)) {
        for (const nid of p.topic_node_ids) neededNodeIds.add(nid);
      }
    }
  }

  // --- one consolidated node-title fetch -----------------------------------
  let nodeTitle: Record<string, string> = {};
  if (neededNodeIds.size > 0) {
    const { data: nodes } = await adminClient
      .from("nodes")
      .select("id, title")
      .in("id", [...neededNodeIds]);
    nodeTitle = Object.fromEntries(
      (nodes ?? []).map((n: { id: string; title: string }) => [n.id, n.title]),
    );
  }

  // --- assemble per kind ----------------------------------------------------
  for (const p of problemRows) {
    const topic = p.topic_node_id ? nodeTitle[p.topic_node_id] : undefined;
    if (topic) topicsByRefId[p.id] = [topic];
    const title = p.title || topic;
    if (title) titleByRefId[p.id] = title;
  }

  for (const e of engagements) {
    const paper = e.paper_id ? paperById[e.paper_id] : undefined;
    if (!paper) continue;
    if (paper.title) titleByRefId[e.id] = paper.title;
    const topics = paper.topic_node_ids.map((nid) => nodeTitle[nid]).filter(Boolean) as string[];
    if (topics.length > 0) topicsByRefId[e.id] = topics;
  }

  for (const nodeId of [...conceptNodeIds, ...suggestedNodeIds]) {
    const title = nodeTitle[nodeId];
    if (!title) continue;
    // A concept review's title IS the node; a suggested_interest has no title,
    // so the node surfaces as its topic chip. Both set the topic; concept also
    // sets the title (DailyView suppresses the chip when it equals the title).
    topicsByRefId[nodeId] = [title];
    if (conceptNodeIds.includes(nodeId)) titleByRefId[nodeId] = title;
  }

  return items.map((item) => ({
    ...item,
    title: item.ref_id ? (titleByRefId[item.ref_id] ?? null) : null,
    topics: item.ref_id ? (topicsByRefId[item.ref_id] ?? []) : [],
    in_progress: item.ref_id ? (inProgressByRefId[item.ref_id] ?? false) : false,
  }));
}

export async function getOrSurfacePick(
  supabase: SupabaseClient,
  userId: string,
): Promise<QueueResult> {
  // 1. Look for an existing open surfaced_picks row (replaced_at IS NULL).
  const { data: openPick } = await supabase
    .from("surfaced_picks")
    .select("id, queue_item_ids")
    .eq("user_id", userId)
    .is("replaced_at", null)
    .order("surfaced_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (openPick) {
    const ids: string[] = openPick.queue_item_ids as string[];

    if (ids.length > 0) {
      const { data: rows } = await supabase
        .from("queue_items")
        .select(
          "id, kind, ref_id, added_reason, time_estimate_minutes_low, time_estimate_minutes_high, state, via_refresher",
        )
        .in("id", ids);

      const active = (rows ?? []).filter(
        (r) => !["done", "dismissed", "skipped", "deferred"].includes(r.state as string),
      );

      if (active.length > 0) {
        const items = await resolveTitles(active.map(toItem));
        return {
          pick_id: openPick.id as string,
          items,
          more_coming: items.length < 3,
        };
      }
    }

    // Pick is stale (all items consumed or empty) — close it and surface fresh below.
    await supabase
      .from("surfaced_picks")
      .update({ replaced_at: new Date().toISOString() })
      .eq("id", openPick.id as string);

    // Reset any items from this pick that are still 'surfaced' back to 'pending'
    // so surface-daily can re-pick them. Items already done/dismissed/skipped stay as-is.
    if (ids.length > 0) {
      await supabase
        .from("queue_items")
        .update({ state: "pending" })
        .in("id", ids)
        .eq("state", "surfaced");
    }
  }

  // 2. No open pick (or stale pick just closed) — call Python /surface-daily.
  try {
    const result = await surfaceDaily({ userId });
    const items = await resolveTitles(result.items.map(toItem));
    return {
      pick_id: result.pick_id,
      items,
      more_coming: items.length < 3,
    };
  } catch (err) {
    if (is404(err)) {
      // Empty queue — nothing pending yet. Kick a background refill so an
      // active user who burned through their queue gets restocked.
      maybeRefillQueue(userId, 0);
      return { pick_id: null, items: [], more_coming: true };
    }
    throw err;
  }
}
