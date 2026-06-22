import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { submitNodeReadiness, type NodeReadinessState } from "@/lib/pythonApi";

// Thin proxy to the Python /add-interest/node-readiness endpoint (Phase 13
// Step 3). Writes node-level user_node_states from the coarse readiness pass
// that replaced the subtopic concept tour.

interface Body {
  user_interest_id: string;
  node_states: Array<{ node_id: string; state: NodeReadinessState }>;
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

  if (!body.user_interest_id || !Array.isArray(body.node_states)) {
    return NextResponse.json(
      { error: "user_interest_id and node_states are required" },
      { status: 400 },
    );
  }

  try {
    await submitNodeReadiness({
      userId: user.id,
      userInterestId: body.user_interest_id,
      nodeStates: body.node_states.map((s) => ({
        nodeId: s.node_id,
        state: s.state,
      })),
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
