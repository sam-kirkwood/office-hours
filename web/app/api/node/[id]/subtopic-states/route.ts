import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// GET /api/node/[id]/subtopic-states
//
// Returns the signed-in user's per-subtopic states for the given foundation
// node, plus any cached subtopic glosses from node_concept_briefs (Step 5.5).
// Used by NodePanel's Subtopics section in the skill tree (phase-10-rev
// Step 6, survey-and-difficulty-design.md §7).

interface SubtopicGloss {
  slug: string;
  title?: string;
  gloss_md?: string;
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: nodeId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const admin = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const [statesRes, briefRes] = await Promise.all([
    admin
      .from("user_subtopic_states")
      .select("subtopic_slug, state")
      .eq("user_id", user.id)
      .eq("node_id", nodeId),
    admin
      .from("node_concept_briefs")
      .select("subtopic_glosses_json")
      .eq("node_id", nodeId)
      .maybeSingle(),
  ]);

  const states = (statesRes.data ?? []) as Array<{ subtopic_slug: string; state: string }>;
  const glosses = (briefRes.data?.subtopic_glosses_json ?? []) as SubtopicGloss[];

  return NextResponse.json({
    states,
    glosses,
  });
}
