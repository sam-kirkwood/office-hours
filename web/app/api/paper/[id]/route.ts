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
    .select("id, kind, ref_id, state")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!queueItem) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { data: engagement } = await adminClient
    .from("paper_engagements")
    .select(
      "id, user_id, paper_id, why_this_md, orienting_concepts_json, questions_json, state, current_question_index, created_at, updated_at, completed_at",
    )
    .eq("id", queueItem.ref_id)
    .maybeSingle();

  if (!engagement) return NextResponse.json({ error: "Engagement not found" }, { status: 404 });

  const { data: paper } = await adminClient
    .from("papers")
    .select("id, title, authors_json, year, arxiv_id, doi, external_url, abstract_md")
    .eq("id", engagement.paper_id)
    .maybeSingle();

  const { data: answers } = await adminClient
    .from("paper_answers")
    .select("id, engagement_id, question_id, user_response_md, claude_response_md, submitted_at")
    .eq("engagement_id", engagement.id);

  return NextResponse.json({ queueItem, engagement, paper, answers: answers ?? [] });
}
