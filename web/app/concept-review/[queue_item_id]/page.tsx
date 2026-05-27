import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { conceptReviewResolve } from "@/lib/pythonApi";
import ConceptReadingView from "@/components/ConceptReadingView";

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

  const result = await conceptReviewResolve({
    userId: user.id,
    queueItemId,
  });

  if (result.kind === "problem" && result.queue_item_id) {
    redirect(`/problem/${result.queue_item_id}`);
  }

  if (result.kind !== "reading" || !result.node) {
    redirect("/daily");
  }

  return (
    <ConceptReadingView queueItemId={queueItemId} node={result.node} />
  );
}
