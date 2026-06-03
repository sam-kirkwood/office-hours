import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import type { Node, Edge } from "@/lib/types";

// GET /api/node/[id]/neighbors
//
// Returns the 1-hop neighbors of the given node — every node connected by
// at least one edge — plus the edges themselves so the client knows the
// relationship type per neighbor. Used by NodePanel to render its
// "Connected topics" section (Step 6 follow-up, node-driven what's-nearby).
//
// Unlike /api/graph/me (which is scoped to the user's interests + 1-hop
// adjacent), this surface answers "what does this specific node connect
// to?" regardless of whether the neighbors are in the user's interest set.

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

  // Edges where this node is the source OR the target.
  const { data: edgeRows } = await admin
    .from("edges")
    .select("*")
    .or(`source_node_id.eq.${nodeId},target_node_id.eq.${nodeId}`);

  const edges = (edgeRows ?? []) as Edge[];
  const neighborIds = new Set<string>();
  for (const e of edges) {
    if (e.source_node_id !== nodeId) neighborIds.add(e.source_node_id);
    if (e.target_node_id !== nodeId) neighborIds.add(e.target_node_id);
  }

  if (neighborIds.size === 0) {
    return NextResponse.json({ neighbors: [], edges: [] });
  }

  const { data: nodeRows } = await admin
    .from("nodes")
    .select("*")
    .in("id", [...neighborIds]);

  return NextResponse.json({
    neighbors: (nodeRows ?? []) as Node[],
    edges,
  });
}
