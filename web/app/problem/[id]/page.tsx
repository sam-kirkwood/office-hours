import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import ProblemView from "@/components/ProblemView";
import type { Problem, ProblemHint, Attempt } from "@/lib/types";

export default async function ProblemPage({
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
  if (
    queueItem.state === "done" ||
    queueItem.state === "dismissed" ||
    queueItem.state === "deferred"
  ) {
    redirect("/daily");
  }

  const { data: problem } = await adminClient
    .from("problems")
    .select("id, topic_node_id, title, statement_md, difficulty, intent, context_hook_id, context_md, created_at")
    .eq("id", queueItem.ref_id)
    .maybeSingle();

  if (!problem) redirect("/daily");

  // Topic title for the problem's metadata line (d11). The interest a problem
  // is drawn from is its topic node; resolve the title from `nodes`.
  let topicTitle: string | null = null;
  if (problem.topic_node_id) {
    const { data: node } = await adminClient
      .from("nodes")
      .select("title")
      .eq("id", problem.topic_node_id)
      .maybeSingle();
    topicTitle = node?.title ?? null;
  }

  const { data: hints } = await adminClient
    .from("problem_hints")
    .select("id, problem_id, level, text, part_label")
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

  const existingAttempt = (attempts?.[0] ?? null) as Attempt | null;

  return (
    <main className="min-h-screen bg-background">
      <ProblemView
        queueItemId={queueItemId}
        problem={problem as Problem}
        topicTitle={topicTitle}
        hints={(hints ?? []) as ProblemHint[]}
        existingAttempt={existingAttempt}
      />
    </main>
  );
}
