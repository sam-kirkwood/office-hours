import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// POST /api/problem/[id]/defer
// User tapped "not ready yet — come back later" on a problem before
// starting work. Transitions the queue item to state='deferred' and stamps
// deferred_at = now() so Step 3's /check-deferred has the signal.
//
// Distinct from skip (which writes an attempt with marked_refreshed=true)
// and dismiss (negative preference). Defer is "I want this, but not now —
// the prerequisites need to land first" (survey-and-difficulty-design.md
// §3.5). No attempts row, no user_node_states change.
//
// Only valid before the user starts working — rejects when state is
// in_progress/done/skipped/dismissed/deferred.

const ALLOWED_PRIOR_STATES = new Set(["pending", "surfaced"]);

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: queueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: queueItem } = await adminClient
    .from("queue_items")
    .select("id, state")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!queueItem) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  if (!ALLOWED_PRIOR_STATES.has(queueItem.state as string)) {
    return NextResponse.json(
      { error: `Cannot defer from state '${queueItem.state}'` },
      { status: 409 },
    );
  }

  const now = new Date().toISOString();
  const { error } = await adminClient
    .from("queue_items")
    .update({ state: "deferred", deferred_at: now, updated_at: now })
    .eq("id", queueItemId)
    .eq("user_id", user.id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
