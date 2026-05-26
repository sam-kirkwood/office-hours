import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, loadSurveyDraft } from "@/lib/surveyState";
import { suggestSurveyInterests } from "@/lib/pythonApi";
import { buildDomainInputs } from "@/lib/surveyDomains";

// GET /api/survey/suggestions
// Reads the user's persisted Stage 1 + Stage 2 selections and asks the Python
// /survey/suggest-interests endpoint to rerank a shortlist of interest-kind
// nodes into 6–10 tiles. Per-domain sub-areas and relationship cards are
// expanded into the payload so the Haiku rerank prompt can use the signal.

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const admin = getAdminClient();
    const draft = await loadSurveyDraft(admin, user.id);

    const refreshSlugs = Object.entries(draft.node_ratings_json)
      .filter(([, v]) => v === "refresh")
      .map(([slug]) => slug);

    const markedFoundationNodeIds: string[] = [];
    if (refreshSlugs.length > 0) {
      const { data: nodes } = await admin
        .from("nodes")
        .select("id, slug")
        .in("slug", refreshSlugs);
      for (const n of nodes ?? []) markedFoundationNodeIds.push(n.id as string);
    }

    const domains = buildDomainInputs(draft.background_json.domains);

    const result = await suggestSurveyInterests({
      userId: user.id,
      domains,
      markedFoundationNodeIds,
    });

    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
