import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { gradeSolution } from "@/lib/pythonApi";

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

  const { attempt_id, user_edited_markdown } = await request.json();
  if (!attempt_id || typeof user_edited_markdown !== "string") {
    return NextResponse.json({ error: "attempt_id and user_edited_markdown required" }, { status: 400 });
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: attempt } = await adminClient
    .from("attempts")
    .select("id, user_id")
    .eq("id", attempt_id)
    .eq("queue_item_id", queueItemId)
    .maybeSingle();

  if (!attempt) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (attempt.user_id !== user.id) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const result = await gradeSolution({
    userId: user.id,
    attemptId: attempt_id,
    userEditedMarkdown: user_edited_markdown,
  });

  await adminClient
    .from("queue_items")
    .update({ state: "done", updated_at: new Date().toISOString() })
    .eq("id", queueItemId);

  // Post-attempt node-state update + adaptive queue actions are handled by
  // /assess-engagement, which /grade-solution invokes as a best-effort hook
  // (api/routes/grade_solution.py:135). No additional curator call needed here.

  return NextResponse.json({
    grade_response_md: result.grade_response_md,
    notebook_entry_id: result.notebook_entry_id,
  });
}
