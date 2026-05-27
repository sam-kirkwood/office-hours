// Server-side helper shared by the GET /api/queue route and the daily server
// component. Avoids an intra-process HTTP round-trip.

import type { SupabaseClient } from "@supabase/supabase-js";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { surfaceDaily } from "@/lib/pythonApi";
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
  subject_kind?: string | null;
  subject_queue_item_id?: string | null;
}): SurfacedQueueItem {
  return {
    queue_item_id: (raw.id ?? raw.queue_item_id)!,
    kind: raw.kind,
    ref_id: raw.ref_id,
    added_reason: raw.added_reason,
    time_estimate_minutes_low: raw.time_estimate_minutes_low,
    time_estimate_minutes_high: raw.time_estimate_minutes_high,
    subject_kind: raw.subject_kind ?? null,
    subject_queue_item_id: raw.subject_queue_item_id ?? null,
  };
}


export async function resolveTitles(items: SurfacedQueueItem[]): Promise<SurfacedQueueItem[]> {
  const problemIds = items
    .filter((i) => i.kind === "problem" && i.ref_id)
    .map((i) => i.ref_id as string);

  const engagementIds = items
    .filter((i) => i.kind === "paper_engagement" && i.ref_id)
    .map((i) => i.ref_id as string);

  const conceptNodeIds = items
    .filter((i) => i.kind === "concept_review" && i.ref_id)
    .map((i) => i.ref_id as string);

  if (
    problemIds.length === 0 &&
    engagementIds.length === 0 &&
    conceptNodeIds.length === 0
  ) {
    return items;
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const titleByRefId: Record<string, string> = {};

  if (problemIds.length > 0) {
    const { data: problems } = await adminClient
      .from("problems")
      .select("id, title, topic_node_id")
      .in("id", problemIds);

    const untitled: Array<{ id: string; topic_node_id: string }> = [];
    for (const p of problems ?? []) {
      if (p.title) {
        titleByRefId[p.id] = p.title;
      } else if (p.topic_node_id) {
        untitled.push({ id: p.id, topic_node_id: p.topic_node_id });
      }
    }

    if (untitled.length > 0) {
      const nodeIds = untitled.map((p) => p.topic_node_id);
      const { data: nodes } = await adminClient
        .from("nodes")
        .select("id, title")
        .in("id", nodeIds);
      const nodeTitle: Record<string, string> = Object.fromEntries(
        (nodes ?? []).map((n: { id: string; title: string }) => [n.id, n.title]),
      );
      for (const p of untitled) {
        if (nodeTitle[p.topic_node_id]) titleByRefId[p.id] = nodeTitle[p.topic_node_id];
      }
    }
  }

  if (engagementIds.length > 0) {
    const { data: engagements } = await adminClient
      .from("paper_engagements")
      .select("id, paper_id")
      .in("id", engagementIds);

    const paperIds = (engagements ?? [])
      .map((e: { id: string; paper_id: string }) => e.paper_id)
      .filter(Boolean) as string[];

    if (paperIds.length > 0) {
      const { data: papers } = await adminClient
        .from("papers")
        .select("id, title")
        .in("id", paperIds);

      const paperTitle: Record<string, string> = Object.fromEntries(
        (papers ?? []).map((p: { id: string; title: string }) => [p.id, p.title]),
      );

      for (const e of engagements ?? []) {
        if (e.paper_id && paperTitle[e.paper_id]) {
          titleByRefId[e.id] = paperTitle[e.paper_id];
        }
      }
    }
  }

  if (conceptNodeIds.length > 0) {
    const { data: nodes } = await adminClient
      .from("nodes")
      .select("id, title")
      .in("id", conceptNodeIds);
    for (const n of nodes ?? []) {
      if (n.title) titleByRefId[n.id] = n.title as string;
    }
  }

  return items.map((item) => ({
    ...item,
    title: item.ref_id ? (titleByRefId[item.ref_id] ?? null) : null,
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
          "id, kind, ref_id, added_reason, time_estimate_minutes_low, time_estimate_minutes_high, state",
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
      // Empty queue — nothing pending yet.
      return { pick_id: null, items: [], more_coming: true };
    }
    throw err;
  }
}
