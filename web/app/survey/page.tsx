import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getAdminClient, loadSurveyDraft, nextStage } from "@/lib/surveyState";
import RestartSurveyButton from "@/components/survey/RestartSurveyButton";

// Entry point. Redirects the user to whichever stage they should be on:
// — first incomplete stage if mid-survey
// — /daily if the survey is finished (non-admins)
// — for admins with a finished survey, renders a tiny "restart?" surface
//   so iterative testing doesn't require a DB poke.

export default async function SurveyEntry() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const next = nextStage(draft.completed_stages);

  if (next !== "done") {
    redirect(`/survey/${next}`);
  }

  const isAdmin = !!process.env.ADMIN_EMAIL && user.email === process.env.ADMIN_EMAIL;
  if (!isAdmin) {
    redirect("/daily");
  }

  return (
    <div className="mx-auto max-w-2xl px-5 py-16 text-center">
      <h1 className="font-serif text-2xl text-foreground">Survey already finished.</h1>
      <p className="mt-3 text-sm text-muted-foreground">
        You&apos;re seeing this because you&apos;re signed in as the admin account.
        Restart wipes your survey, interests, node states, and queue items so
        you can re-walk the seven stages.
      </p>
      <div className="mt-8 flex items-center justify-center gap-3">
        <a
          href="/daily"
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground transition-colors duration-[var(--duration-fast)] hover:border-foreground/30 hover:text-foreground"
        >
          Go to daily
        </a>
        <RestartSurveyButton />
      </div>
    </div>
  );
}
