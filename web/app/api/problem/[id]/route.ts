import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export async function GET(
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
    .select("id, kind, ref_id, state, added_reason")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!queueItem) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { data: problem } = await adminClient
    .from("problems")
    .select("id, topic_node_id, statement_md, difficulty, context_hook_id, context_md, created_at")
    .eq("id", queueItem.ref_id)
    .maybeSingle();

  if (!problem) return NextResponse.json({ error: "Problem not found" }, { status: 404 });

  const { data: hints } = await adminClient
    .from("problem_hints")
    .select("id, problem_id, level, text")
    .eq("problem_id", problem.id)
    .order("level", { ascending: true });

  const { data: attempts } = await adminClient
    .from("attempts")
    .select(
      "id, user_id, problem_id, queue_item_id, raw_image_paths, parsed_markdown, user_edited_markdown, hint_levels_used, parse_status, grade_response_md, submitted_at, marked_refreshed, created_at",
    )
    .eq("user_id", user.id)
    .eq("queue_item_id", queueItemId)
    .is("submitted_at", null)
    .order("created_at", { ascending: false })
    .limit(1);

  return NextResponse.json({
    queueItem,
    problem,
    hints: hints ?? [],
    existingAttempt: attempts?.[0] ?? null,
  });
}
