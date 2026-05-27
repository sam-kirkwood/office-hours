import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";

// Stage 4 + 5 closeout. Called by DialogOrchestrator once it has walked
// every parsed segment + concept tour. Clears pending_interests_json and
// marks the `dialog` stage complete.

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "dialog", {
      pending_interests_json: {},
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
