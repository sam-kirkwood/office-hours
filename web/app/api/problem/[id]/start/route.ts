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

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: queueItem } = await adminClient
    .from("queue_items")
    .select("id, ref_id")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!queueItem) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const body = await request.json().catch(() => ({}));
  const hintLevelsUsed = Array.isArray(body.hint_levels_used) ? body.hint_levels_used : [];

  const { data: attempt, error } = await adminClient
    .from("attempts")
    .insert({
      user_id: user.id,
      problem_id: queueItem.ref_id,
      queue_item_id: queueItemId,
      hint_levels_used: hintLevelsUsed,
      parse_status: "pending",
      raw_image_paths: [],
    })
    .select("id")
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ attempt_id: attempt.id });
}
