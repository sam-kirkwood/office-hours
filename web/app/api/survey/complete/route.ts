import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";
import { updateQueue, suggestPapers, proposePapers } from "@/lib/pythonApi";

// Stage 7 finalize. Marks `confirm` complete and best-effort kicks the queue
// updater + paper suggestions so /daily has cards to show. The curriculum
// curator (Step 3 of Phase 10-rev) replaces these calls later.

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "confirm", {});

    // Best-effort post-survey seeding; failures don't block completion.
    updateQueue({ userId: user.id, trigger: "interest_add" }).catch((err) =>
      console.error("updateQueue failed:", err),
    );
    suggestPapers({ userId: user.id }).catch((err) =>
      console.error("suggestPapers failed:", err),
    );
    proposePapers({ userId: user.id }).catch((err) =>
      console.error("proposePapers failed:", err),
    );

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
