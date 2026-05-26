import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { assertAdminApi } from "@/lib/adminAuth";
import { getAdminClient } from "@/lib/surveyState";

// POST /api/survey/reset (admin only)
// Wipes the calling user's onboarding + engagement state so the seven-stage
// survey can be re-walked from scratch. Intended for iterative testing.
//
// Deletion order matters: attempts.queue_item_id and a handful of other FKs
// don't cascade, so child rows have to go before parents. The list below is
// ordered leaves-first.

const TABLES_IN_DELETE_ORDER = [
  "paper_answers",        // engagement_id → paper_engagements (CASCADE, but explicit is cheap)
  "paper_qa",             // engagement_id → paper_engagements (CASCADE)
  "paper_engagements",    // user_id → profiles
  "notebook_entries",     // generic ref_id pointer; no FK but tied to attempts/engagements
  "attempts",             // queue_item_id → queue_items (NO cascade — this is what blocked us)
  "surfaced_picks",       // chosen_item_id → queue_items (SET NULL); user_id → profiles
  "queue_items",          // user_id → profiles
  "user_interests",       // user_id → profiles
  "user_node_states",     // user_id → profiles
  "bookmarks",            // user_id → profiles
  "refresher_schedule",   // user_id → profiles
  "surveys",              // user_id → profiles
] as const;

export async function POST() {
  const adminErr = await assertAdminApi();
  if (adminErr) return adminErr;

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const admin = getAdminClient();
    const cleared: string[] = [];

    // paper_answers and paper_qa scope by engagement, not user. Look up the
    // user's engagement IDs first so we can clear those children before
    // dropping the engagement rows.
    const { data: engagements } = await admin
      .from("paper_engagements")
      .select("id")
      .eq("user_id", user.id);
    const engagementIds = (engagements ?? []).map((e: { id: string }) => e.id);

    for (const table of TABLES_IN_DELETE_ORDER) {
      let query = admin.from(table).delete();
      if (table === "paper_answers" || table === "paper_qa") {
        if (engagementIds.length === 0) {
          cleared.push(`${table}: skipped (no engagements)`);
          continue;
        }
        query = query.in("engagement_id", engagementIds);
      } else {
        query = query.eq("user_id", user.id);
      }
      const { error } = await query;
      if (error) throw new Error(`${table}: ${error.message}`);
      cleared.push(table);
    }

    return NextResponse.json({ ok: true, cleared });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
