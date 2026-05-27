import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";

interface Body {
  // Slugs of Stage-3 suggestion tiles the user selected.
  selected_slugs: string[];
  // "Anything else?" free text — fed to Stage 4 (add-interest dialog).
  free_text: string;
}

// Stage 3 advance: persist the user's selections to
// surveys.pending_interests_json and mark the `interests` stage complete.
// The dialog walk happens in Stage 4 at /survey/dialog (client-driven, calls
// /api/add-interest/parse and /resolve directly).

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

  const selectedSlugs = (body.selected_slugs ?? []).filter((s) => typeof s === "string");
  const freeText = (body.free_text ?? "").trim();

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "interests", {
      pending_interests_json: { tile_slugs: selectedSlugs, free_text: freeText },
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
