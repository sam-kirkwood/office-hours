import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const PYTHON_API_URL = process.env.PYTHON_API_URL!;
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN!;

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

  const { engagement_id, question_id, user_response_md } = await request.json();
  if (!engagement_id || !question_id || typeof user_response_md !== "string") {
    return NextResponse.json({ error: "engagement_id, question_id, and user_response_md required" }, { status: 400 });
  }

  const res = await fetch(`${PYTHON_API_URL}/grade-paper-answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${INTERNAL_API_TOKEN}`,
    },
    body: JSON.stringify({
      user_id: user.id,
      engagement_id,
      question_id,
      user_response_md,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    return NextResponse.json({ error: text }, { status: res.status });
  }

  const data = await res.json();

  // Update queue_item state to in_progress when the user answers the first question
  const { createClient: createAdminClient } = await import("@supabase/supabase-js");
  const admin = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );
  await admin
    .from("queue_items")
    .update({ state: "in_progress", updated_at: new Date().toISOString() })
    .eq("id", queueItemId)
    .eq("state", "surfaced");

  // When the user finishes the last question, /grade-paper-answer's
  // /assess-engagement hook (api/routes/grade_paper_answer.py:147) records
  // the engagement-complete signal. No additional curator call needed here;
  // the daily /run-daily-planner pass will pick up the new state.

  return NextResponse.json(data);
}
