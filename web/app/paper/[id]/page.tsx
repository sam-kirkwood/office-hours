import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import PaperView from "@/components/PaperView";
import type { Paper, PaperEngagement, PaperAnswer } from "@/lib/types";

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: queueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

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

  if (!queueItem) redirect("/daily");
  if (queueItem.state === "done" || queueItem.state === "dismissed") redirect("/daily");

  const { data: engagement } = await adminClient
    .from("paper_engagements")
    .select(
      "id, user_id, paper_id, why_this_md, orienting_concepts_json, questions_json, state, current_question_index, created_at, updated_at, completed_at",
    )
    .eq("id", queueItem.ref_id)
    .maybeSingle();

  if (!engagement) redirect("/daily");

  const { data: paper } = await adminClient
    .from("papers")
    .select("id, title, authors_json, year, arxiv_id, doi, external_url, abstract_md, created_at")
    .eq("id", engagement.paper_id)
    .maybeSingle();

  if (!paper) redirect("/daily");

  const { data: answers } = await adminClient
    .from("paper_answers")
    .select("id, engagement_id, question_id, user_response_md, claude_response_md, submitted_at")
    .eq("engagement_id", engagement.id);

  return (
    <main className="min-h-screen bg-background">
      <PaperView
        queueItemId={queueItemId}
        paper={paper as Paper}
        engagement={engagement as PaperEngagement}
        existingAnswers={(answers ?? []) as PaperAnswer[]}
      />
    </main>
  );
}
