import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient } from "@/lib/surveyState";

// Returns the caller's user_interests row for a single node, if it exists.
// Used to:
//  - SurveyNodePanel Edit — pre-fills the dialog with the existing
//    intent_context so the user is editing, not typing from scratch.
//  - RequestBox "is this already an interest?" check for §2.7 Case 2 vs Case 1.
//
// Query: either ?node_id=<uuid> or ?node_slug=<slug>. Returns 200 with
// {exists: false, intent_context: ""} when no row, so the client doesn't
// have to special-case 404s.

export async function GET(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(request.url);
  const nodeId = searchParams.get("node_id");
  const nodeSlug = searchParams.get("node_slug");

  if (!nodeId && !nodeSlug) {
    return NextResponse.json(
      { error: "node_id or node_slug required" },
      { status: 400 },
    );
  }

  try {
    const admin = getAdminClient();

    let resolvedNodeId = nodeId;
    if (!resolvedNodeId && nodeSlug) {
      const { data: node } = await admin
        .from("nodes")
        .select("id")
        .eq("slug", nodeSlug)
        .maybeSingle();
      if (!node) {
        return NextResponse.json({
          exists: false,
          intent_context: "",
          node_id: null,
        });
      }
      resolvedNodeId = node.id as string;
    }

    const { data } = await admin
      .from("user_interests")
      .select("id, intent_context, added_via")
      .eq("user_id", user.id)
      .eq("node_id", resolvedNodeId!)
      .maybeSingle();

    if (!data) {
      return NextResponse.json({
        exists: false,
        intent_context: "",
        node_id: resolvedNodeId,
      });
    }
    return NextResponse.json({
      exists: true,
      intent_context: data.intent_context ?? "",
      added_via: data.added_via,
      node_id: resolvedNodeId,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
