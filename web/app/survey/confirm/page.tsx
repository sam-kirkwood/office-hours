import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import ConfirmGraph from "@/components/survey/ConfirmGraph";
import type { Node, Edge, UserNodeState } from "@/lib/types";

interface UserNodeEntry {
  node: Node;
  state: UserNodeState | null;
}

export default async function ConfirmPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const gate = gateFor("confirm", draft.completed_stages);
  if (gate === "done") redirect("/daily");
  if (gate !== null) redirect(`/survey/${gate}`);

  // Same shape as /api/graph/me — replicated here so server-side render has
  // the data ready without an extra round-trip.
  const { data: interests } = await admin
    .from("user_interests")
    .select("node_id")
    .eq("user_id", user.id);
  const interestNodeIds = (interests ?? []).map((i: { node_id: string }) => i.node_id);

  const { data: states } = await admin
    .from("user_node_states")
    .select("user_id, node_id, state, engagement_count, struggle_score, last_engaged_at")
    .eq("user_id", user.id);
  const stateByNodeId: Record<string, UserNodeState> = Object.fromEntries(
    (states ?? []).map((s: UserNodeState) => [s.node_id, s]),
  );

  const stateNodeIds = (states ?? []).map((s: UserNodeState) => s.node_id);
  const allUserNodeIds = Array.from(new Set([...interestNodeIds, ...stateNodeIds]));

  const { data: allNodes } = await admin.from("nodes").select("*");
  const nodeById: Record<string, Node> = Object.fromEntries(
    (allNodes ?? []).map((n: Node) => [n.id, n]),
  );

  const userNodes: UserNodeEntry[] = allUserNodeIds
    .filter((id) => nodeById[id])
    .map((id) => ({ node: nodeById[id], state: stateByNodeId[id] ?? null }));

  const { data: allEdges } = await admin.from("edges").select("*");
  const userNodeIdSet = new Set(allUserNodeIds);
  const edges = ((allEdges ?? []) as Edge[]).filter(
    (e) => userNodeIdSet.has(e.source_node_id) || userNodeIdSet.has(e.target_node_id),
  );

  const adjacentIds = new Set<string>();
  for (const e of edges) {
    if (!userNodeIdSet.has(e.source_node_id)) adjacentIds.add(e.source_node_id);
    if (!userNodeIdSet.has(e.target_node_id)) adjacentIds.add(e.target_node_id);
  }
  const adjacentNodes = Array.from(adjacentIds)
    .filter((id) => nodeById[id])
    .map((id) => nodeById[id]);

  return (
    <ConfirmGraph
      initialGraphData={{
        user_nodes: userNodes,
        adjacent_nodes: adjacentNodes,
        edges,
      }}
      interestNodeIds={interestNodeIds}
    />
  );
}
