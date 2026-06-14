import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

type Readiness = "solid" | "learning";

// An explicit user mark is authoritative — overwrite both state and
// struggle_score so the two columns don't contradict each other.
// (The curator reads both; a stale high struggle_score + 'comfortable' is
// self-contradictory.)
const READINESS_TO_NODE_STATE: Record<Readiness, { state: string; struggle_score: number }> = {
  solid: { state: "comfortable", struggle_score: 0.0 },
  learning: { state: "active", struggle_score: 0.3 }, // neutral, not stale-high
};

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await request.json().catch(() => ({}));
  const { node_id, readiness } = body as { node_id?: string; readiness?: string };

  if (!node_id || !readiness || !(readiness in READINESS_TO_NODE_STATE)) {
    return NextResponse.json(
      { error: "node_id and readiness (solid|learning) required" },
      { status: 400 },
    );
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { state, struggle_score } = READINESS_TO_NODE_STATE[readiness as Readiness];
  const now = new Date().toISOString();

  await adminClient
    .from("user_node_states")
    .upsert(
      {
        user_id: user.id,
        node_id,
        state,
        struggle_score,
        updated_at: now,
      },
      { onConflict: "user_id,node_id" },
    );

  return NextResponse.json({ ok: true, state });
}
