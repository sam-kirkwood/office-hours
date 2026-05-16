import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import type { Node, Edge, UserNodeState } from "@/lib/types";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  // 1. User interest node IDs
  const { data: interests } = await adminClient
    .from("user_interests")
    .select("node_id")
    .eq("user_id", user.id);

  const interestNodeIds = (interests ?? []).map((i: { node_id: string }) => i.node_id);

  // 2. User node states
  const { data: states } = await adminClient
    .from("user_node_states")
    .select("user_id, node_id, state, engagement_count, struggle_score, last_engaged_at")
    .eq("user_id", user.id);

  const stateByNodeId: Record<string, UserNodeState> = Object.fromEntries(
    (states ?? []).map((s: UserNodeState) => [s.node_id, s]),
  );

  // Foundation nodes with state (not already in interests)
  const stateNodeIds = (states ?? []).map((s: UserNodeState) => s.node_id);
  const allUserNodeIds = [...new Set([...interestNodeIds, ...stateNodeIds])];

  // 3. All nodes (at this scale, load all and filter)
  const { data: allNodes } = await adminClient.from("nodes").select("*");
  const nodeById: Record<string, Node> = Object.fromEntries(
    (allNodes ?? []).map((n: Node) => [n.id, n]),
  );

  const userNodes = allUserNodeIds
    .filter((id) => nodeById[id])
    .map((id) => ({ node: nodeById[id], state: stateByNodeId[id] ?? null }));

  // 4. All edges — filter to those touching user nodes
  const { data: allEdges } = await adminClient.from("edges").select("*");
  const userNodeIdSet = new Set(allUserNodeIds);
  const edges = ((allEdges ?? []) as Edge[]).filter(
    (e) => userNodeIdSet.has(e.source_node_id) || userNodeIdSet.has(e.target_node_id),
  );

  // 5. Adjacent node IDs: edge endpoints not in user nodes
  const adjacentIds = new Set<string>();
  for (const e of edges) {
    if (!userNodeIdSet.has(e.source_node_id)) adjacentIds.add(e.source_node_id);
    if (!userNodeIdSet.has(e.target_node_id)) adjacentIds.add(e.target_node_id);
  }

  const adjacentNodes = [...adjacentIds].filter((id) => nodeById[id]).map((id) => nodeById[id]);

  return NextResponse.json({ user_nodes: userNodes, adjacent_nodes: adjacentNodes, edges });
}
