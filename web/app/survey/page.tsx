import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SurveyForm from "@/components/SurveyForm";
import type { Node } from "@/lib/types";

export default async function SurveyPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const { data: nodes } = await supabase
    .from("nodes")
    .select("id, slug, title, description_md, domain, kind, difficulty_hint, subtopics_json, pool_status, created_at")
    .eq("pool_status", "active")
    .order("kind")
    .order("difficulty_hint");

  return (
    <main className="min-h-screen bg-white">
      <SurveyForm nodes={(nodes ?? []) as Node[]} />
    </main>
  );
}
