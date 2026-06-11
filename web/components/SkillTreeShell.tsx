"use client";

import SkillTreeView from "@/components/SkillTreeView";
import SkillTreeListView from "@/components/SkillTreeListView";
import { useIsMobile } from "@/lib/useIsMobile";
import type { Node as AppNode, Edge as AppEdge, UserNodeState } from "@/lib/types";

interface GraphData {
  user_nodes: Array<{ node: AppNode; state: UserNodeState | null }>;
  adjacent_nodes: AppNode[];
  edges: AppEdge[];
}

interface Props {
  graphData: GraphData;
  // n2: open this node's panel on load (deep-link from notebook / profile).
  initialNodeId?: string;
}

// Branches the skill-tree render: ReactFlow on tablet+; list view on phone.
// First paint shows the desktop graph and switches once useIsMobile resolves
// after mount — the brief swap is acceptable, and the page is already inside
// a client island.

export default function SkillTreeShell({ graphData, initialNodeId }: Props) {
  const isMobile = useIsMobile();
  if (isMobile) {
    return <SkillTreeListView graphData={graphData} />;
  }
  return (
    <div style={{ width: "100%", height: "calc(100vh - 49px)" }}>
      <SkillTreeView graphData={graphData} initialNodeId={initialNodeId} />
    </div>
  );
}
