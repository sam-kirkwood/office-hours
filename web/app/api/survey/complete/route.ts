import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";
import { planQueue, proposePapers } from "@/lib/pythonApi";

// Stage 7 finalize. Marks `confirm` complete and best-effort kicks the
// curriculum curator's daily-planner for this user (cold-start path per
// curriculum-curator-design.md §13.1). The Sonnet plan fans out problem +
// refresher items; papers are NOT part of the planner (curator_plan.py forbids
// them), so for the cold-start queue to honour the user's mode balance we also
// seed paper engagements here when the slider gives papers a meaningful share
// (Phase 10.5-rev d17). Both calls are best-effort and don't block completion.

// mode_balance: 0.0 = all problems, 1.0 = all papers. Below this, skip the
// cold-start paper seed (the user wants problems).
const PAPER_SEED_MIN_BALANCE = 0.3;

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "confirm", {});

    planQueue({ userId: user.id, triggeredBy: "cold_start" }).catch((err) =>
      console.error("planQueue failed:", err),
    );

    // Seed papers if the user's mode balance asks for them.
    const { data: survey } = await admin
      .from("surveys")
      .select("mode_balance")
      .eq("user_id", user.id)
      .maybeSingle();
    const modeBalance = survey?.mode_balance ?? 0.5;
    if (modeBalance >= PAPER_SEED_MIN_BALANCE) {
      proposePapers({ userId: user.id, modeBalance }).catch((err) =>
        console.error("proposePapers failed:", err),
      );
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
