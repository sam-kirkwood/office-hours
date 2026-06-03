"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import type { Node as RFNode, Edge as RFEdge, NodeProps } from "@xyflow/react";
import { graphlib, layout as dagreLayout } from "@dagrejs/dagre";
import NodePanel from "@/components/NodePanel";
import EdgePanel from "@/components/EdgePanel";
import type { Node as AppNode, Edge as AppEdge, UserNodeState } from "@/lib/types";

interface GraphData {
  user_nodes: Array<{ node: AppNode; state: UserNodeState | null }>;
  adjacent_nodes: AppNode[];
  edges: AppEdge[];
}

// ---------------------------------------------------------------------------
// Node dimensions — square so rounded-full produces true circles
// ---------------------------------------------------------------------------

const USER_W = 130;
const USER_H = 130;
const ADJ_W = 108;
const ADJ_H = 108;

// ---------------------------------------------------------------------------
// State → style classes (card-like, 1px borders, amber/forest accents)
// ---------------------------------------------------------------------------

function stateClasses(state: UserNodeState | null): string {
  const s = state?.state ?? "unseen";
  const map: Record<string, string> = {
    unseen:
      "border border-border bg-card text-foreground",
    bookmarked:
      "border border-amber/50 bg-[var(--amber-subtle)] text-foreground",
    active:
      "border-2 border-primary bg-[var(--amber-subtle)] text-foreground",
    struggling:
      "border border-destructive/30 bg-destructive/[0.07] text-foreground",
    comfortable:
      "border border-[var(--forest)]/50 bg-[var(--forest-subtle)] text-foreground",
  };
  return map[s] ?? map.unseen;
}

// Warm edge tones matching the page palette
const EDGE_STROKE = "#b8ac9f";
const EDGE_STROKE_RELATED = "#cec6bc";

// ---------------------------------------------------------------------------
// Custom node components
// ---------------------------------------------------------------------------

const handleStyle = { opacity: 0, pointerEvents: "none" as const };

function UserNode({ data }: NodeProps) {
  const { node, state, highlighted } = data as {
    node: AppNode;
    state: UserNodeState | null;
    highlighted?: boolean;
  };
  return (
    <div
      className={`flex h-full w-full items-center justify-center rounded-full px-4 text-center font-serif text-[10px] leading-[1.35] ${stateClasses(state)} ${highlighted ? "ring-2 ring-[var(--forest)] ring-offset-2 ring-offset-[var(--background)] transition-all duration-[var(--duration-standard)]" : ""}`}
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      {node.title}
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

function AdjacentNode({ data }: NodeProps) {
  const { node, highlighted } = data as { node: AppNode; highlighted?: boolean };
  return (
    <div
      className={`flex h-full w-full items-center justify-center rounded-full border border-dashed border-border/50 bg-background px-3 text-center font-serif text-[9.5px] leading-[1.35] text-muted-foreground/55 ${highlighted ? "ring-2 ring-[var(--forest)] ring-offset-2 ring-offset-[var(--background)] transition-all duration-[var(--duration-standard)]" : ""}`}
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      {node.title}
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

const nodeTypes = { user: UserNode, adjacent: AdjacentNode };

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

const LEGEND_STATES = [
  { label: "Unseen", cls: "border border-border bg-card" },
  { label: "Active", cls: "border-2 border-primary bg-[var(--amber-subtle)]" },
  { label: "Comfortable", cls: "border border-[var(--forest)]/50 bg-[var(--forest-subtle)]" },
  { label: "Bookmarked", cls: "border border-amber/50 bg-[var(--amber-subtle)]" },
  { label: "Struggling", cls: "border border-destructive/30 bg-destructive/[0.07]" },
] as const;

function Legend() {
  return (
    <div className="absolute bottom-4 left-4 z-10 rounded-md border border-border bg-card px-3.5 py-3">
      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        Legend
      </p>
      <div className="flex flex-col gap-1.5">
        {LEGEND_STATES.map(({ label, cls }) => (
          <div key={label} className="flex items-center gap-2">
            <div className={`h-4 w-4 rounded-full ${cls}`} />
            <span className="text-[11px] text-muted-foreground">{label}</span>
          </div>
        ))}
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 rounded-full border border-dashed border-border/50 bg-background" />
          <span className="text-[11px] text-muted-foreground">Nearby</span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dagre layout
// ---------------------------------------------------------------------------

function buildLayout(graphData: GraphData): { nodes: RFNode[]; edges: RFEdge[] } {
  const g = new graphlib.Graph();
  g.setGraph({ rankdir: "TB", ranksep: 70, nodesep: 24 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const { node } of graphData.user_nodes) {
    g.setNode(node.id, { width: USER_W, height: USER_H });
  }
  for (const node of graphData.adjacent_nodes) {
    g.setNode(node.id, { width: ADJ_W, height: ADJ_H });
  }
  for (const edge of graphData.edges) {
    if (g.hasNode(edge.source_node_id) && g.hasNode(edge.target_node_id)) {
      g.setEdge(edge.source_node_id, edge.target_node_id);
    }
  }

  dagreLayout(g);

  const rfNodes: RFNode[] = [
    ...graphData.user_nodes.map(({ node, state }) => ({
      id: node.id,
      type: "user",
      position: {
        x: (g.node(node.id)?.x ?? 0) - USER_W / 2,
        y: (g.node(node.id)?.y ?? 0) - USER_H / 2,
      },
      style: { width: USER_W, height: USER_H },
      data: { node, state },
    })),
    ...graphData.adjacent_nodes.map((node) => ({
      id: node.id,
      type: "adjacent",
      position: {
        x: (g.node(node.id)?.x ?? 0) - ADJ_W / 2,
        y: (g.node(node.id)?.y ?? 0) - ADJ_H / 2,
      },
      style: { width: ADJ_W, height: ADJ_H },
      data: { node, state: null },
    })),
  ];

  const renderedIds = new Set(rfNodes.map((n) => n.id));

  const rfEdges: RFEdge[] = graphData.edges
    .filter((e) => renderedIds.has(e.source_node_id) && renderedIds.has(e.target_node_id))
    .map((edge) => ({
      id: edge.id,
      source: edge.source_node_id,
      target: edge.target_node_id,
      animated: false,
      style:
        edge.edge_kind === "related"
          ? { strokeDasharray: "4,4", stroke: EDGE_STROKE_RELATED, strokeWidth: 1 }
          : { stroke: EDGE_STROKE, strokeWidth: 1 },
      markerEnd:
        edge.edge_kind === "prerequisite"
          ? { type: MarkerType.ArrowClosed, color: EDGE_STROKE, width: 14, height: 14 }
          : undefined,
    }));

  return { nodes: rfNodes, edges: rfEdges };
}

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

interface SelectedEntry {
  node: AppNode;
  state: UserNodeState | null;
}

interface Props {
  graphData: GraphData;
  // Optional override so callers can swap in a context-specific panel (e.g.
  // the Stage 7 onboarding confirmation uses a panel that exposes Delete /
  // Edit on the user's interests rather than the post-onboarding action set).
  renderPanel?: (args: {
    entry: SelectedEntry;
    isUserNode: boolean;
    onClose: () => void;
    onHighlightNeighbors?: (neighborIds: string[]) => void;
  }) => React.ReactNode;
  // Optional legend override. Pass a node to render instead of the default;
  // pass `null` to render no legend at all. Callers like the Stage 7
  // confirmation use a simplified two-entry legend keyed to that surface's
  // visual contract.
  legend?: React.ReactNode | null;
}

function SkillTreeViewInner({ graphData, renderPanel, legend }: Props) {
  const [rfNodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());

  const reactFlow = useReactFlow();
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (graphData.user_nodes.length === 0 && graphData.adjacent_nodes.length === 0) return;
    const { nodes, edges } = buildLayout(graphData);
    setNodes(nodes);
    setEdges(edges);
  }, [graphData, setNodes, setEdges]);

  // Re-tag rfNodes with `highlighted` whenever the highlighted set changes.
  useEffect(() => {
    setNodes((existing) =>
      existing.map((n) => ({
        ...n,
        data: { ...n.data, highlighted: highlightedIds.has(n.id) },
      })),
    );
  }, [highlightedIds, setNodes]);

  // Clear any pending highlight timer on unmount.
  useEffect(() => {
    return () => {
      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
    };
  }, []);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: RFNode) => {
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
  }, []);

  const onEdgeClick = useCallback((_event: React.MouseEvent, edge: RFEdge) => {
    setSelectedEdgeId(edge.id);
    setSelectedNodeId(null);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, []);

  // Called by NodePanel's "Highlight on canvas" action. Takes the IDs of
  // nodes to highlight (typically the selected node + its 1-hop neighbors),
  // applies a ring style to whichever are present in the rendered graph,
  // and pans/zooms to fit them. Auto-clears after a few seconds.
  const handleHighlightNeighbors = useCallback(
    (neighborIds: string[]) => {
      if (!selectedNodeId) return;
      const focusIds = [selectedNodeId, ...neighborIds];
      const renderedIds = new Set(rfNodes.map((n) => n.id));
      const visibleFocus = focusIds.filter((id) => renderedIds.has(id));
      if (visibleFocus.length === 0) return;
      setHighlightedIds(new Set(visibleFocus));
      // Fit view to those nodes with some padding.
      reactFlow.fitView({
        nodes: visibleFocus.map((id) => ({ id })),
        padding: 0.3,
        duration: 350,
      });
      if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
      highlightTimerRef.current = setTimeout(() => {
        setHighlightedIds(new Set());
      }, 4000);
    },
    [rfNodes, reactFlow, selectedNodeId],
  );

  const userNodeIdSet = new Set(graphData.user_nodes.map((un) => un.node.id));
  const allNodesById = new Map<string, AppNode>();
  for (const un of graphData.user_nodes) allNodesById.set(un.node.id, un.node);
  for (const n of graphData.adjacent_nodes) allNodesById.set(n.id, n);

  const selectedEntry: SelectedEntry | null = selectedNodeId
    ? graphData.user_nodes.find((un) => un.node.id === selectedNodeId) ??
      (() => {
        const adj = allNodesById.get(selectedNodeId);
        return adj ? { node: adj, state: null } : null;
      })()
    : null;

  const selectedEdge = selectedEdgeId
    ? graphData.edges.find((e) => e.id === selectedEdgeId) ?? null
    : null;

  const isEmpty = graphData.user_nodes.length === 0 && graphData.adjacent_nodes.length === 0;

  if (isEmpty) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <p className="mb-1 text-sm font-medium text-foreground">No nodes yet.</p>
          <p className="text-sm text-muted-foreground">
            Complete the survey to add interests to your graph.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        style={{ background: "var(--background)" }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="var(--border)"
        />
        <Controls
          style={{
            backgroundColor: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
          }}
        />
      </ReactFlow>

      {legend === undefined ? <Legend /> : legend}

      {selectedEntry &&
        (renderPanel ? (
          renderPanel({
            entry: selectedEntry,
            isUserNode: userNodeIdSet.has(selectedEntry.node.id),
            onClose: () => setSelectedNodeId(null),
            onHighlightNeighbors: handleHighlightNeighbors,
          })
        ) : (
          <NodePanel
            node={selectedEntry.node}
            state={selectedEntry.state}
            isUserNode={userNodeIdSet.has(selectedEntry.node.id)}
            onClose={() => setSelectedNodeId(null)}
            onHighlightNeighbors={handleHighlightNeighbors}
            onSelectNode={(id) => setSelectedNodeId(id)}
          />
        ))}

      {selectedEdge && (
        <EdgePanel
          edge={selectedEdge}
          sourceNode={allNodesById.get(selectedEdge.source_node_id)}
          targetNode={allNodesById.get(selectedEdge.target_node_id)}
          onClose={() => setSelectedEdgeId(null)}
        />
      )}
    </div>
  );
}

export default function SkillTreeView(props: Props) {
  return (
    <ReactFlowProvider>
      <SkillTreeViewInner {...props} />
    </ReactFlowProvider>
  );
}
