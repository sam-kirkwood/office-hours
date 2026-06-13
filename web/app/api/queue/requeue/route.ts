import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/queue/requeue   body: { queue_item_id }
//
// "Queue it now" (§A2) for a bookmarked item: the user manages the return, and
// this is them pulling it back. Flips the queue item 'bookmarked' → 'pending'
// (mirror of /api/queue/resume for deferred items) and retires the matching
// bookmark row by stamping promoted_at, so it leaves the "Come back to this"
// tab while keeping the history.
//
// Only valid for problem/paper bookmarks, which have a backing queue item.
// Node bookmarks (from the skill tree) have no queue slot — they keep the
// "See in skill tree" path instead.

const NODE_KINDS = new Set(["concept_review", "suggested_interest"]);

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let queueItemId: string | undefined;
  try {
    ({ queue_item_id: queueItemId } = (await request.json()) as { queue_item_id?: string });
  } catch {
    return NextResponse.json({ error: "Invalid body" }, { status: 400 });
  }
  if (!queueItemId?.trim()) {
    return NextResponse.json({ error: "queue_item_id is required" }, { status: 400 });
  }

  const admin = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: item } = await admin
    .from("queue_items")
    .select("id, kind, ref_id, state")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (item.state !== "bookmarked") {
    return NextResponse.json(
      { error: `Cannot requeue from state '${item.state}'` },
      { status: 409 },
    );
  }

  // Flip back into the active rotation.
  const now = new Date().toISOString();
  const { error: updErr } = await admin
    .from("queue_items")
    .update({ state: "pending", updated_at: now })
    .eq("id", queueItemId)
    .eq("user_id", user.id);
  if (updErr) return NextResponse.json({ error: updErr.message }, { status: 500 });

  // Retire the matching bookmark (same content resolution as the save path).
  let bookmarkKind: "node" | "problem" | "paper" | null = null;
  let refId: string | null = item.ref_id;
  if (item.kind === "problem") {
    bookmarkKind = "problem";
  } else if (NODE_KINDS.has(item.kind)) {
    bookmarkKind = "node";
  } else if (item.kind === "paper_engagement" && item.ref_id) {
    bookmarkKind = "paper";
    const { data: eng } = await admin
      .from("paper_engagements")
      .select("paper_id")
      .eq("id", item.ref_id)
      .maybeSingle();
    refId = eng?.paper_id ?? null;
  }

  if (bookmarkKind && refId) {
    await admin
      .from("bookmarks")
      .update({ promoted_at: now })
      .eq("user_id", user.id)
      .eq("kind", bookmarkKind)
      .eq("ref_id_or_text", refId)
      .is("promoted_at", null);
  }

  return NextResponse.json({ ok: true });
}
