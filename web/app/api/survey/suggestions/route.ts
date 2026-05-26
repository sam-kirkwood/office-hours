import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient } from "@/lib/surveyState";
import { suggestSurveyInterests } from "@/lib/pythonApi";

// GET /api/survey/suggestions
// Reads the user's persisted Stage 1 + Stage 2 selections from the surveys
// row and the user_node_states, then asks the Python /survey/suggest-interests
// route to rerank a shortlist of interest-kind nodes into 6–10 tiles.

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const admin = getAdminClient();

    const { data: survey } = await admin
      .from("surveys")
      .select("background_json, node_ratings_json")
      .eq("user_id", user.id)
      .maybeSingle();

    const background = (survey?.background_json ?? {}) as {
      domain_chips?: string[];
    };
    const ratings = (survey?.node_ratings_json ?? {}) as Record<string, string>;

    const refreshSlugs = Object.entries(ratings)
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

    const domainChips = (background.domain_chips ?? []).filter(
      (s): s is string => typeof s === "string",
    );

    const result = await suggestSurveyInterests({
      userId: user.id,
      domainChips,
      markedFoundationNodeIds,
    });

    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
