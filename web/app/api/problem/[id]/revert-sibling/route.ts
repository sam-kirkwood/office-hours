import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/problem/[id]/revert-sibling
//
// The user is on a too-hard sibling and wants the original back.
// [id] = the sibling's queue_item_id.
//
// 1. Load the sibling queue_item → get parent_queue_item_id (the original).
// 2. Flip the original back to 'pending'.
// 3. Flip the sibling to 'superseded' (it's the rejected version now).
// 4. Return { parent_queue_item_id } so the client can navigate.
//
// Net: the rejected sibling can't resurface; the original returns to
// normal rotation and can be worked on.

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: siblingQueueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: sibling } = await adminClient
    .from("queue_items")
    .select("id, state, parent_queue_item_id")
    .eq("id", siblingQueueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!sibling) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (!sibling.parent_queue_item_id) {
    return NextResponse.json({ error: "No parent to revert to" }, { status: 400 });
  }

  const now = new Date().toISOString();

  await Promise.all([
    // Restore original to the active rotation
    adminClient
      .from("queue_items")
      .update({ state: "pending", priority_score: 0.85, updated_at: now })
      .eq("id", sibling.parent_queue_item_id)
      .eq("user_id", user.id),
    // Retire the rejected sibling
    adminClient
      .from("queue_items")
      .update({ state: "superseded", updated_at: now })
      .eq("id", siblingQueueItemId)
      .eq("user_id", user.id),
  ]);

  return NextResponse.json({ parent_queue_item_id: sibling.parent_queue_item_id });
}
