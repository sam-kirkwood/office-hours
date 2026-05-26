import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import BackgroundForm from "@/components/survey/BackgroundForm";

export default async function BackgroundPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const gate = gateFor("background", draft.completed_stages);
  if (gate === "done") redirect("/daily");
  if (gate !== null) redirect(`/survey/${gate}`);

  const bg = draft.background_json ?? {};
  return (
    <BackgroundForm
      initialDomainChips={bg.domain_chips ?? []}
      initialRelationshipCards={bg.relationship_cards ?? []}
      initialShortText={draft.free_text_intent ?? ""}
    />
  );
}
