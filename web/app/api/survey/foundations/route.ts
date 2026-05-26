import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";

interface Body {
  // Slugs of foundation nodes the user marked for refresh.
  refresh_slugs: string[];
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

  const refreshSlugs = (body.refresh_slugs ?? []).filter((s) => typeof s === "string");

  try {
    const admin = getAdminClient();

    // Build the node_ratings_json shape: {slug: 'refresh'} for marked tiles only.
    const node_ratings_json: Record<string, "refresh"> = {};
    for (const slug of refreshSlugs) node_ratings_json[slug] = "refresh";

    await upsertSurveyStage(admin, user.id, "foundations", { node_ratings_json });

    // Write user_node_states for the refresh-flagged nodes (state = 'active'
    // per survey-and-difficulty-design.md §1.3.5).
    if (refreshSlugs.length > 0) {
      const { data: nodes } = await admin
        .from("nodes")
        .select("id, slug")
        .in("slug", refreshSlugs);

      const stateRows = (nodes ?? []).map((n: { id: string; slug: string }) => ({
        user_id: user.id,
        node_id: n.id,
        state: "active" as const,
      }));

      if (stateRows.length > 0) {
        const { error } = await admin
          .from("user_node_states")
          .upsert(stateRows, { onConflict: "user_id,node_id" });
        if (error) console.error("user_node_states upsert failed:", error);
      }
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
