import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/queue/dismiss   body: { queue_item_id }
//
// "Not for me" (§A1): the user doesn't want this / wants less of it. Writes the
// negative terminal state 'dismissed' on the queue item. This is the honest
// down-weight signal — for a suggested_interest, compute_cross_pollination
// already reads dismissed nodes to down-weight that domain. (Curator-side
// consumption of dismissed problem/paper *topics* as a preference penalty is a
// flagged follow-up; the signal is recorded here, kind-agnostically.)
//
// Distinct from "I know this" (+comfort, advance), "Bookmark" (positive save),
// and "Not ready" (defer → system-managed return). Replaces the old
// dismiss-via-/api/queue/bookmark smell (resolved decision 6): "Not for me" must
// write a dismiss, not a bookmark.

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
    .select("id")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();
  if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { error } = await admin
    .from("queue_items")
    .update({ state: "dismissed", updated_at: new Date().toISOString() })
    .eq("id", queueItemId)
    .eq("user_id", user.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
