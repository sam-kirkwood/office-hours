import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import PlanGraph from "@/components/PlanGraph";
import type { PlanNode, CanonicalTopic, CanonicalEdge } from "@/lib/types";

export default async function PlanPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const { data: plan } = await supabase
    .from("user_plans")
    .select("id")
    .eq("user_id", user.id)
    .eq("status", "pending_review")
    .maybeSingle();

  if (!plan) redirect("/");

  const [{ data: planNodes }, { data: allTopics }, { data: allEdges }] = await Promise.all([
    supabase
      .from("plan_nodes")
      .select("*, canonical_topics(*)")
      .eq("plan_id", plan.id)
      .order("order_index"),
    supabase.from("canonical_topics").select("*"),
    supabase.from("canonical_edges").select("*"),
  ]);

  return (
    <main className="min-h-screen p-6 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900">Your Learning Plan</h1>
        <p className="text-zinc-500 text-sm mt-1">
          Review the topics you built. Approve to start, or request changes.
        </p>
      </div>
      <PlanGraph
        planId={plan.id}
        planNodes={(planNodes ?? []) as PlanNode[]}
        allTopics={(allTopics ?? []) as CanonicalTopic[]}
        allEdges={(allEdges ?? []) as CanonicalEdge[]}
      />
    </main>
  );
}
