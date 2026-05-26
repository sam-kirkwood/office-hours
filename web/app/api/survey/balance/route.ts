import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";

interface Body {
  // 0 = all problems, 1 = all papers. Stored in surveys.mode_balance.
  mode_balance: number;
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const raw = Number(body.mode_balance);
  const mode_balance = Number.isFinite(raw) ? Math.min(1, Math.max(0, raw)) : 0.5;

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "balance", { mode_balance });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
