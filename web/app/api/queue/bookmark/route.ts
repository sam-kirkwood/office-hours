import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/queue/bookmark   body: { queue_item_id }
//
// "Bookmark" (§A2): save this, find it later, I manage the return. A polymorphic
// save over the queue's kinds, landing a row in the `bookmarks` table (the
// durable index for the notebook's "Come back to this" tab) and taking the queue
// item out of the active rotation via state='bookmarked' (a positive terminal
// state, distinct from 'dismissed' / 'done' — see migration 20250034).
//
// The bookmark references the *durable content*, not the queue slot, so queue
// churn never loses it:
//   · problem          → kind 'problem', ref = problems.id          (ref_id)
//   · paper_engagement  → kind 'paper',  ref = paper_engagements.paper_id
//   · concept_review    → kind 'node',   ref = nodes.id             (ref_id)
//   · suggested_interest→ kind 'node',   ref = nodes.id             (ref_id)
//
// Distinct from "Not ready" (defer → system-managed return) and "Not for me"
// (dismiss → negative signal). "Queue it now" (/api/queue/requeue) brings it back.

// queue kind → (bookmarks.kind). Papers need a ref_id hop (engagement → paper).
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
  if (!item.ref_id) {
    return NextResponse.json({ error: "Item has no content to save" }, { status: 400 });
  }

  // Resolve (bookmark kind, content ref).
  let bookmarkKind: "node" | "problem" | "paper";
  let refId: string;
  if (item.kind === "problem") {
    bookmarkKind = "problem";
    refId = item.ref_id;
  } else if (NODE_KINDS.has(item.kind)) {
    bookmarkKind = "node";
    refId = item.ref_id;
  } else if (item.kind === "paper_engagement") {
    bookmarkKind = "paper";
    const { data: eng } = await admin
      .from("paper_engagements")
      .select("paper_id")
      .eq("id", item.ref_id)
      .maybeSingle();
    if (!eng?.paper_id) {
      return NextResponse.json({ error: "Paper not found" }, { status: 404 });
    }
    refId = eng.paper_id;
  } else {
    return NextResponse.json(
      { error: `Cannot bookmark a '${item.kind}' item` },
      { status: 400 },
    );
  }

  // Idempotent save: reuse an existing un-promoted bookmark for this content.
  const { data: existing } = await admin
    .from("bookmarks")
    .select("id")
    .eq("user_id", user.id)
    .eq("kind", bookmarkKind)
    .eq("ref_id_or_text", refId)
    .is("promoted_at", null)
    .maybeSingle();

  if (!existing) {
    const { error: insErr } = await admin.from("bookmarks").insert({
      user_id: user.id,
      kind: bookmarkKind,
      ref_id_or_text: refId,
    });
    if (insErr) return NextResponse.json({ error: insErr.message }, { status: 500 });
  }

  // Take the queue item out of the active rotation (positive terminal state).
  const { error: updErr } = await admin
    .from("queue_items")
    .update({ state: "bookmarked", updated_at: new Date().toISOString() })
    .eq("id", queueItemId)
    .eq("user_id", user.id);
  if (updErr) return NextResponse.json({ error: updErr.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
