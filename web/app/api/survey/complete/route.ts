import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";
import { planQueue } from "@/lib/pythonApi";

// Stage 7 finalize. Marks `confirm` complete and best-effort kicks the
// curriculum curator's daily-planner for this user (cold-start path per
// curriculum-curator-design.md §13.1). The Sonnet plan fans out queue items
// for the user's interests; paper engagement recommendations are part of the
// curator's job. Failures don't block survey completion.

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

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
