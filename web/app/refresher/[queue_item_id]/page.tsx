import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { refresherResolve } from "@/lib/pythonApi";

export default async function RefresherResolverPage({
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

  const result = await refresherResolve({ userId: user.id, queueItemId });

  if (result.kind === "problem") redirect(`/problem/${result.queue_item_id}`);
  if (result.kind === "paper_engagement") redirect(`/paper/${result.queue_item_id}`);
  if (result.kind === "concept_review")
    redirect(`/concept-review/${result.queue_item_id}`);

  redirect("/daily");
}
