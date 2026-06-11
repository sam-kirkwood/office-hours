import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { surfaceDaily, maybeRefillQueue } from "@/lib/pythonApi";
import { toItem, resolveTitles } from "@/lib/queueHelpers";

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    // 1. Find the current open pick.
    const { data: currentPick } = await supabase
      .from("surfaced_picks")
      .select("id, queue_item_ids")
      .eq("user_id", user.id)
      .is("replaced_at", null)
      .maybeSingle();

    if (currentPick) {
      const ids = (currentPick.queue_item_ids ?? []) as string[];
      // Reset still-surfaced items to pending so surface-daily can pick them up again.
      // Items already done/dismissed/skipped are left as-is.
      if (ids.length > 0) {
        await supabase
          .from("queue_items")
          .update({ state: "pending" })
          .in("id", ids)
          .eq("state", "surfaced");
      }
      const replacedAt = new Date().toISOString();
      await supabase
        .from("surfaced_picks")
        .update({ replaced_at: replacedAt })
        .eq("id", currentPick.id);

      // Reroll signal capture (Phase 10-rev §3e). For each item the user
      // passed over, write a length-1 surfaced_picks row with
      // chosen_item_id=null. The curator's recent_engagement.reroll_patterns
      // (api/curator_inputs.py:load_recent_engagement) counts these by node
      // on the next /plan-queue pass. Per-item rows so the count is by node,
      // not by pick. See curriculum-curator-design.md §16.
      if (ids.length > 0) {
        const passOverRows = ids.map((id) => ({
          user_id: user.id,
          queue_item_ids: [id],
          chosen_item_id: null,
          surfaced_at: replacedAt,
          replaced_at: replacedAt,
        }));
        await supabase.from("surfaced_picks").insert(passOverRows);
      }
    }

    // 2. Create a new pick.
    const result = await surfaceDaily({ userId: user.id });
    const items = await resolveTitles(result.items.map(toItem));
    return NextResponse.json({
      pick_id: result.pick_id,
      items,
      more_coming: items.length < 3,
    });
  } catch (err) {
    // 404 from Python means no pending items left after reroll.
    if (err instanceof Error && err.message.includes("404")) {
      maybeRefillQueue(user.id, 0);
      return NextResponse.json({ pick_id: null, items: [], more_coming: true });
    }
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
