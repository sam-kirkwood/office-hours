// POST /api/queue/steer — directed reroll with a selection constraint (§A5).
//
// Accepts a steering hint and re-picks from the pending queue without
// generating new content. The same pass-over recording as a plain reroll
// ensures the curator can read the steering pattern.
//
// Body: { hint: "shorter" | "more_papers" | "different" | "less_topic",
//         topic_node_id?: string }
//   - topic_node_id: required for "less_topic" — the node whose problems to
//     deprioritize. Derived by the client from item.topics + item.ref_id.
//
// Pinned items (§A6) survive the steer the same way they survive a plain
// reroll: they are not reset to pending and not recorded as passed-over.

import { createClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { surfaceDaily, maybeRefillQueue } from "@/lib/pythonApi";
import { toItem, resolveTitles } from "@/lib/queueHelpers";

type SteerHint = "shorter" | "more_papers" | "different" | "less_topic";

const VALID_HINTS = new Set<SteerHint>([
  "shorter",
  "more_papers",
  "different",
  "less_topic",
]);

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json()) as { hint?: string; topic_node_id?: string };
  const hint = body.hint as SteerHint | undefined;
  if (!hint || !VALID_HINTS.has(hint)) {
    return NextResponse.json({ error: "Invalid steer hint" }, { status: 400 });
  }

  try {
    // 1. Find the current open pick.
    const { data: currentPick } = await supabase
      .from("surfaced_picks")
      .select("id, queue_item_ids")
      .eq("user_id", user.id)
      .is("replaced_at", null)
      .maybeSingle();

    const nonPinnedShownRefIds: string[] = [];

    if (currentPick) {
      const ids = (currentPick.queue_item_ids ?? []) as string[];

      if (ids.length > 0) {
        // Discover pinned vs non-pinned items in the current pick.
        const { data: itemRows } = await supabase
          .from("queue_items")
          .select("id, ref_id, pinned")
          .in("id", ids);

        const pinnedIds = new Set(
          (itemRows ?? []).filter((r) => r.pinned).map((r) => r.id as string),
        );
        const nonPinnedIds = ids.filter((id) => !pinnedIds.has(id));

        // Collect ref_ids of non-pinned items for the "different" constraint.
        for (const row of itemRows ?? []) {
          if (!row.pinned && row.ref_id) nonPinnedShownRefIds.push(row.ref_id as string);
        }

        // Reset non-pinned surfaced items to pending.
        if (nonPinnedIds.length > 0) {
          await supabase
            .from("queue_items")
            .update({ state: "pending" })
            .in("id", nonPinnedIds)
            .eq("state", "surfaced");
        }

        const replacedAt = new Date().toISOString();
        await supabase
          .from("surfaced_picks")
          .update({ replaced_at: replacedAt })
          .eq("id", currentPick.id);

        // Record pass-over rows for non-pinned items (curator reads steering
        // pattern the same way it reads plain rerolls).
        if (nonPinnedIds.length > 0) {
          const passOverRows = nonPinnedIds.map((id) => ({
            user_id: user.id,
            queue_item_ids: [id],
            chosen_item_id: null,
            surfaced_at: replacedAt,
            replaced_at: replacedAt,
          }));
          await supabase.from("surfaced_picks").insert(passOverRows);
        }
      }
    }

    // 2. Call surface_daily with the steering constraint. Pinned items are
    //    automatically re-included by _load_pinned_surfaced in Python.
    const result = await surfaceDaily({
      userId: user.id,
      steer: hint,
      // "different" passes the ref_ids of what was just shown so they're excluded.
      ...(hint === "different" && nonPinnedShownRefIds.length > 0
        ? { steerExcludedRefIds: nonPinnedShownRefIds }
        : {}),
      // "less_topic" passes the topic node id to filter.
      ...(hint === "less_topic" && body.topic_node_id
        ? { steerTopicNodeId: body.topic_node_id }
        : {}),
    });

    const items = await resolveTitles(result.items.map(toItem));
    return NextResponse.json({
      pick_id: result.pick_id,
      items,
      more_coming: items.length < 3,
      pending_remaining: result.pending_remaining ?? 0,
    });
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) {
      maybeRefillQueue(user.id, 0);
      return NextResponse.json({ pick_id: null, items: [], more_coming: true, pending_remaining: 0 });
    }
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
