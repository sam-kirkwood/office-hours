import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SurveyForm from "@/components/SurveyForm";
import type { CanonicalTopic, CanonicalEdge } from "@/lib/types";

export default async function SurveyPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const [{ data: topics }, { data: edges }] = await Promise.all([
    supabase.from("canonical_topics").select("*").order("domain").order("difficulty_band"),
    supabase.from("canonical_edges").select("*"),
  ]);

  return (
    <main className="min-h-screen bg-white">
      <SurveyForm
        topics={(topics ?? []) as CanonicalTopic[]}
        edges={(edges ?? []) as CanonicalEdge[]}
      />
    </main>
  );
}
