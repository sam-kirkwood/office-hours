import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: queueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await request.json();
  const { attempt_id, level } = body;
  if (!attempt_id || typeof level !== "number") {
    return NextResponse.json({ error: "attempt_id and level required" }, { status: 400 });
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: attempt } = await adminClient
    .from("attempts")
    .select("id, user_id, hint_levels_used")
    .eq("id", attempt_id)
    .eq("queue_item_id", queueItemId)
    .maybeSingle();

  if (!attempt) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (attempt.user_id !== user.id) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const current: number[] = (attempt.hint_levels_used as number[]) ?? [];
  const updated = current.includes(level) ? current : [...current, level].sort((a, b) => a - b);

  await adminClient.from("attempts").update({ hint_levels_used: updated }).eq("id", attempt_id);

  return NextResponse.json({ ok: true });
}
