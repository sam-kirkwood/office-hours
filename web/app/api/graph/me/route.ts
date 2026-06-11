import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import type { Node, Edge, UserNodeState } from "@/lib/types";

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // 1. User interest node IDs
  const { data: interests } = await supabase
    .from("user_interests")
    .select("node_id")
    .eq("user_id", user.id);

  const interestNodeIds = (interests ?? []).map((i: { node_id: string }) => i.node_id);

  // 2. User node states
  const { data: states } = await supabase
    .from("user_node_states")
    .select("user_id, node_id, state, engagement_count, struggle_score, last_engaged_at")
    .eq("user_id", user.id);

  const stateByNodeId: Record<string, UserNodeState> = Object.fromEntries(
    (states ?? []).map((s: UserNodeState) => [s.node_id, s]),
  );

  // 2b. Node bookmarks — orthogonal "come back to this" markers. Folded into
  // the user-node set so bookmarked adjacent nodes render with the amber
  // overlay rather than staying greyed-out neighbours.
  const { data: bookmarks } = await supabase
    .from("bookmarks")
    .select("ref_id_or_text")
    .eq("user_id", user.id)
    .eq("kind", "node");
  const bookmarkedNodeIds = new Set(
    (bookmarks ?? []).map((b: { ref_id_or_text: string }) => b.ref_id_or_text),
  );

  // Foundation nodes with state (not already in interests)
  const stateNodeIds = (states ?? []).map((s: UserNodeState) => s.node_id);
  const allUserNodeIds = [
    ...new Set([...interestNodeIds, ...stateNodeIds, ...bookmarkedNodeIds]),
  ];

  // 3. All nodes (at this scale, load all and filter)
  const { data: allNodes } = await supabase.from("nodes").select("*");
  const nodeById: Record<string, Node> = Object.fromEntries(
    (allNodes ?? []).map((n: Node) => [n.id, n]),
  );

  // isUserNode: an interest or engaged node (vs a bookmark-only marker). Bookmark
  // -only nodes render but still offer "Add / promote to interest" in the panel.
  const interestIdSet = new Set(interestNodeIds);
  const stateIdSet = new Set(stateNodeIds);
  const userNodes = allUserNodeIds
    .filter((id) => nodeById[id])
    .map((id) => ({
      node: nodeById[id],
      state: stateByNodeId[id] ?? null,
      bookmarked: bookmarkedNodeIds.has(id),
      isUserNode: interestIdSet.has(id) || stateIdSet.has(id),
    }));

  // 4. All edges — filter to those touching user nodes
  const { data: allEdges } = await supabase.from("edges").select("*");
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
