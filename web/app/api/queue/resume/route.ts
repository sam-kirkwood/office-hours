import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/queue/resume   body: { queue_item_id }
//
// The user pulled a deferred ("come back to this") item back into the queue
// manually, from the notebook's Come back to this tab (g1). Inverse of
// /api/problem/[id]/defer: flips state='deferred' → 'pending' so the surfacing
// logic can pick it up. Distinct from the curator's automatic /check-deferred,
// which only re-queues once prerequisites land. deferred_at is left intact for
// analytics.

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
    .select("id, state")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (item.state !== "deferred") {
    return NextResponse.json(
      { error: `Cannot resume from state '${item.state}'` },
      { status: 409 },
    );
  }

  const { error } = await admin
    .from("queue_items")
    .update({ state: "pending", updated_at: new Date().toISOString() })
    .eq("id", queueItemId)
    .eq("user_id", user.id);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
