import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getAdminClient, loadSurveyDraft, nextStage } from "@/lib/surveyState";

// Entry point. Redirects the user to whichever stage they should be on:
// — first incomplete stage if mid-survey
// — /daily if the survey is finished

export default async function SurveyEntry() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const next = nextStage(draft.completed_stages);
  if (next === "done") redirect("/daily");
  redirect(`/survey/${next}`);
}
