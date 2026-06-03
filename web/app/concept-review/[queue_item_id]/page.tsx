import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { conceptReviewResolve } from "@/lib/pythonApi";
import ConceptReadingView from "@/components/ConceptReadingView";

async function loadParentPaperBackLink(parentQueueItemId: string): Promise<
  { queue_item_id: string; paper_title: string } | null
> {
  const admin = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );
  const { data: parent } = await admin
    .from("queue_items")
    .select("id, kind, ref_id")
    .eq("id", parentQueueItemId)
    .maybeSingle();
  if (!parent || parent.kind !== "paper_engagement" || !parent.ref_id) return null;

  const { data: engagement } = await admin
    .from("paper_engagements")
    .select("paper_id")
    .eq("id", parent.ref_id)
    .maybeSingle();
  if (!engagement?.paper_id) return null;

  const { data: paper } = await admin
    .from("papers")
    .select("title")
    .eq("id", engagement.paper_id)
    .maybeSingle();
  if (!paper?.title) return null;

  return { queue_item_id: parent.id as string, paper_title: paper.title as string };
}

export default async function ConceptReviewPage({
  params,
}: {
  params: Promise<{ queue_item_id: string }>;
}) {
  const { queue_item_id: queueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  // Pull parent_queue_item_id off the queue row in parallel with the
  // resolve call. The resolve route doesn't surface lineage; reading it
  // here keeps the Python route's response shape focused on the concept.
  const admin = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const [result, parentRow] = await Promise.all([
    conceptReviewResolve({ userId: user.id, queueItemId }),
    admin
      .from("queue_items")
      .select("parent_queue_item_id")
      .eq("id", queueItemId)
      .eq("user_id", user.id)
      .maybeSingle(),
  ]);

  if (result.kind === "problem" && result.queue_item_id) {
    redirect(`/problem/${result.queue_item_id}`);
  }

  if (result.kind !== "reading" || !result.node) {
    redirect("/daily");
  }

  const parentPaper =
    parentRow.data?.parent_queue_item_id
      ? await loadParentPaperBackLink(parentRow.data.parent_queue_item_id as string)
      : null;

  return (
    <ConceptReadingView
      queueItemId={queueItemId}
      node={result.node}
      parentPaper={parentPaper}
    />
  );
}
