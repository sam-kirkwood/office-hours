import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SkillTreeView from "@/components/SkillTreeView";
import type { Node, Edge, UserNodeState } from "@/lib/types";

export default async function SkillTreePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const [{ data: interests }, { data: states }, { data: allNodes }, { data: allEdges }] =
    await Promise.all([
      supabase.from("user_interests").select("node_id").eq("user_id", user.id),
      supabase.from("user_node_states").select("*").eq("user_id", user.id),
      supabase.from("nodes").select("*"),
      supabase.from("edges").select("*"),
    ]);

  const interestNodeIds = (interests ?? []).map((i: { node_id: string }) => i.node_id);
  const stateByNodeId: Record<string, UserNodeState> = Object.fromEntries(
    (states ?? []).map((s: UserNodeState) => [s.node_id, s]),
  );
  const stateNodeIds = (states ?? []).map((s: UserNodeState) => s.node_id);
  const allUserNodeIds = [...new Set([...interestNodeIds, ...stateNodeIds])];

  const nodeById: Record<string, Node> = Object.fromEntries(
    (allNodes ?? []).map((n: Node) => [n.id, n]),
  );

  const userNodeIdSet = new Set(allUserNodeIds);
  const typedEdges = (allEdges ?? []) as Edge[];
  const edges = typedEdges.filter(
    (e) => userNodeIdSet.has(e.source_node_id) || userNodeIdSet.has(e.target_node_id),
  );

  const adjacentIds = new Set<string>();
  for (const e of edges) {
    if (!userNodeIdSet.has(e.source_node_id)) adjacentIds.add(e.source_node_id);
    if (!userNodeIdSet.has(e.target_node_id)) adjacentIds.add(e.target_node_id);
  }

  const userNodes = allUserNodeIds
    .filter((id) => nodeById[id])
    .map((id) => ({ node: nodeById[id], state: stateByNodeId[id] ?? null }));

  const adjacentNodes = [...adjacentIds].filter((id) => nodeById[id]).map((id) => nodeById[id]);

  // Only pass edges where both endpoints are actually in the rendered graph.
  // adjacentIds may contain IDs not in nodeById; those nodes are silently dropped,
  // but the edge would still reference them and confuse React Flow.
  const renderedIds = new Set([...allUserNodeIds.filter((id) => nodeById[id]), ...adjacentNodes.map((n) => n.id)]);
  const filteredEdges = edges.filter(
    (e) => renderedIds.has(e.source_node_id) && renderedIds.has(e.target_node_id),
  );

  const graphData = { user_nodes: userNodes, adjacent_nodes: adjacentNodes, edges: filteredEdges };

  return (
    <main style={{ width: "100%", height: "calc(100vh - 49px)" }}>
      <SkillTreeView graphData={graphData} />
    </main>
  );
}
