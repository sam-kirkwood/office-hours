// Server-side helper shared by the GET /api/queue route and the daily server
// component. Avoids an intra-process HTTP round-trip.

import type { SupabaseClient } from "@supabase/supabase-js";
import { surfaceDaily } from "@/lib/pythonApi";
import type { QueueResult, SurfacedQueueItem } from "@/lib/types";

export type { QueueResult };

function is404(err: unknown): boolean {
  return err instanceof Error && err.message.includes("404");
}

function toItem(raw: {
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
        (r) => !["done", "dismissed", "skipped"].includes(r.state as string),
      );

      if (active.length > 0) {
        return {
          pick_id: openPick.id as string,
          items: active.map(toItem),
          more_coming: active.length < 3,
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
    return {
      pick_id: result.pick_id,
      items: result.items.map(toItem),
      more_coming: result.items.length < 3,
    };
  } catch (err) {
    if (is404(err)) {
      // Empty queue — nothing pending yet.
      return { pick_id: null, items: [], more_coming: true };
    }
    throw err;
  }
}
