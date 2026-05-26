import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import { suggestSurveyInterests } from "@/lib/pythonApi";
import { buildDomainInputs } from "@/lib/surveyDomains";
import InterestSuggestions from "@/components/survey/InterestSuggestions";
import type { SurveyInterestSuggestion } from "@/lib/pythonApi";

export default async function InterestsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const gate = gateFor("interests", draft.completed_stages);
  if (gate === "done") redirect("/daily");
  if (gate !== null) redirect(`/survey/${gate}`);

  const refreshSlugs = Object.entries(draft.node_ratings_json)
    .filter(([, v]) => v === "refresh")
    .map(([slug]) => slug);

  const markedFoundationNodeIds: string[] = [];
  if (refreshSlugs.length > 0) {
    const { data: nodes } = await admin
      .from("nodes")
      .select("id, slug")
      .in("slug", refreshSlugs);
    for (const n of nodes ?? []) markedFoundationNodeIds.push(n.id as string);
  }

  const domains = buildDomainInputs(draft.background_json.domains);

  let suggestions: SurveyInterestSuggestion[] = [];
  try {
    const resp = await suggestSurveyInterests({
      userId: user.id,
      domains,
      markedFoundationNodeIds,
    });
    suggestions = resp.suggestions;
  } catch (err) {
    console.error("suggestSurveyInterests failed; falling back to empty:", err);
  }

  return (
    <InterestSuggestions
      suggestions={suggestions}
      initialSelectedSlugs={draft.pending_interests_json?.tile_slugs ?? []}
      initialFreeText={draft.pending_interests_json?.free_text ?? ""}
    />
  );
}
