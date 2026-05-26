import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";

interface Body {
  domain_chips: string[];
  relationship_cards: string[];
  short_text: string;
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

  const domain_chips = (body.domain_chips ?? []).filter((s) => typeof s === "string");
  const relationship_cards = (body.relationship_cards ?? []).filter((s) => typeof s === "string");
  const short_text = (body.short_text ?? "").trim();

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "background", {
      background_json: { domain_chips, relationship_cards },
      free_text_intent: short_text,
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
