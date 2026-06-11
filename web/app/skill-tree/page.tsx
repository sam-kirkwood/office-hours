import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SkillTreeShell from "@/components/SkillTreeShell";
import type { Node, Edge, UserNodeState } from "@/lib/types";

export default async function SkillTreePage({
  searchParams,
}: {
  searchParams: Promise<{ node?: string }>;
}) {
  const { node: deepLinkSlug } = await searchParams;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const [{ data: interests }, { data: states }, { data: bookmarks }, { data: allNodes }, { data: allEdges }] =
    await Promise.all([
      supabase.from("user_interests").select("node_id").eq("user_id", user.id),
      supabase.from("user_node_states").select("*").eq("user_id", user.id),
      supabase
        .from("bookmarks")
        .select("ref_id_or_text")
        .eq("user_id", user.id)
        .eq("kind", "node"),
      supabase.from("nodes").select("*"),
      supabase.from("edges").select("*"),
    ]);

  const interestNodeIds = (interests ?? []).map((i: { node_id: string }) => i.node_id);
  const stateByNodeId: Record<string, UserNodeState> = Object.fromEntries(
    (states ?? []).map((s: UserNodeState) => [s.node_id, s]),
  );
  const stateNodeIds = (states ?? []).map((s: UserNodeState) => s.node_id);
  // Bookmarked nodes are "come back to this" markers, orthogonal to engagement
  // state. A bookmarked adjacent node has no user_node_states row, so we fold
  // its id into the user-node set so it renders (with the amber overlay) rather
  // than staying a greyed-out neighbour.
  const bookmarkedNodeIds = new Set(
    (bookmarks ?? []).map((b: { ref_id_or_text: string }) => b.ref_id_or_text),
  );
  const allUserNodeIds = [
    ...new Set([...interestNodeIds, ...stateNodeIds, ...bookmarkedNodeIds]),
  ];

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

  // A node is the user's (vs a bookmarked-only "come back to this" marker) when
  // it's an interest or carries engagement state. Bookmark-only nodes render in
  // the graph but still offer "Add / promote to interest" in the panel.
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

  const adjacentNodes = [...adjacentIds].filter((id) => nodeById[id]).map((id) => nodeById[id]);

  // Only pass edges where both endpoints are actually in the rendered graph.
  // adjacentIds may contain IDs not in nodeById; those nodes are silently dropped,
  // but the edge would still reference them and confuse React Flow.
  const renderedIds = new Set([...allUserNodeIds.filter((id) => nodeById[id]), ...adjacentNodes.map((n) => n.id)]);
  const filteredEdges = edges.filter(
    (e) => renderedIds.has(e.source_node_id) && renderedIds.has(e.target_node_id),
  );

  const graphData = { user_nodes: userNodes, adjacent_nodes: adjacentNodes, edges: filteredEdges };

  // n2: resolve the deep-link slug (?node=…) to a node id so the view can open
  // its panel on load. Only honoured when the node is in the rendered slice.
  const renderedNodeIds = new Set([
    ...userNodes.map((u) => u.node.id),
    ...adjacentNodes.map((n) => n.id),
  ]);
  const initialNodeId =
    deepLinkSlug &&
    (allNodes ?? []).find(
      (n: Node) => n.slug === deepLinkSlug && renderedNodeIds.has(n.id),
    )?.id;

  return (
    <main>
      <SkillTreeShell graphData={graphData} initialNodeId={initialNodeId || undefined} />
    </main>
  );
}
