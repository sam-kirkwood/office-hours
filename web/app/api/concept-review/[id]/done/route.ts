import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

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

  const { data: qi } = await adminClient
    .from("queue_items")
    .select("id, kind, state")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!qi) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (qi.kind !== "concept_review") {
    return NextResponse.json(
      { error: "queue_item is not a concept_review" },
      { status: 400 },
    );
  }
  if (qi.state === "done" || qi.state === "dismissed") {
    return NextResponse.json({ ok: true, already_done: true });
  }

  await adminClient
    .from("queue_items")
    .update({ state: "done", updated_at: new Date().toISOString() })
    .eq("id", queueItemId);

  return NextResponse.json({ ok: true });
}
