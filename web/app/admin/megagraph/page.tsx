"use client";

import { useEffect, useState, useCallback } from "react";
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
} from "@xyflow/react";
import type { Node as RFNode, Edge as RFEdge, NodeProps } from "@xyflow/react";
import { graphlib, layout as dagreLayout } from "@dagrejs/dagre";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MegaNode {
  id: string;
  slug: string;
  title: string;
  kind: "foundation" | "interest";
  domain: string;
  pool_status: string;
}

interface MegaEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_kind: string;
  weight: number;
}

interface Snapshot {
  id: string;
  label: string;
  taken_at: string;
  taken_by: string;
}

interface CurationProposal {
  id: string;
  kind: string;
  payload_json: Record<string, string>;
  status: string;
}

interface AdminMegagraphData {
  nodes: MegaNode[];
  edges: MegaEdge[];
  snapshots: Snapshot[];
  pending_proposals: CurationProposal[];
}

interface SnapshotJson {
  nodes: MegaNode[];
  edges: MegaEdge[];
}

// ---------------------------------------------------------------------------
// Node dimensions
// ---------------------------------------------------------------------------

const FOUNDATION_W = 120;
const FOUNDATION_H = 120;
const INTEREST_W = 110;
const INTEREST_H = 110;
const DEPRECATED_W = 90;
const DEPRECATED_H = 90;

const EDGE_STROKE = "#b8ac9f";
const EDGE_STROKE_RELATED = "#cec6bc";

// ---------------------------------------------------------------------------
// Custom node components
// ---------------------------------------------------------------------------

const handleStyle = { opacity: 0, pointerEvents: "none" as const };

function FoundationNode({ data }: NodeProps) {
  const { node, hasProposal } = data as { node: MegaNode; hasProposal: boolean };
  return (
    <div
      className={[
        "flex h-full w-full items-center justify-center rounded-full px-3 text-center font-serif text-[10px] leading-[1.35]",
        "bg-[var(--amber-subtle)] border border-amber/60 text-foreground",
        hasProposal ? "ring-2 ring-orange-400 ring-offset-1 ring-dashed" : "",
      ].join(" ")}
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      {node.title}
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

function InterestNode({ data }: NodeProps) {
  const { node, hasProposal } = data as { node: MegaNode; hasProposal: boolean };
  return (
    <div
      className={[
        "flex h-full w-full items-center justify-center rounded-full px-3 text-center font-serif text-[10px] leading-[1.35]",
        "bg-[var(--forest-subtle)] border border-[var(--forest)]/60 text-foreground",
        hasProposal ? "ring-2 ring-orange-400 ring-offset-1 ring-dashed" : "",
      ].join(" ")}
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      {node.title}
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

function DeprecatedNode({ data }: NodeProps) {
  const { node } = data as { node: MegaNode };
  return (
    <div className="flex h-full w-full items-center justify-center rounded-full border border-dashed border-border bg-muted px-3 text-center font-serif text-[9px] leading-[1.35] text-muted-foreground/60">
      <Handle type="target" position={Position.Top} style={handleStyle} />
      {node.title}
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}

const nodeTypes = {
  foundation: FoundationNode,
  interest: InterestNode,
  deprecated: DeprecatedNode,
};

// ---------------------------------------------------------------------------
// Dagre layout
// ---------------------------------------------------------------------------

function buildLayout(
  nodes: MegaNode[],
  edges: MegaEdge[],
  proposalNodeIds: Set<string>,
): { nodes: RFNode[]; edges: RFEdge[] } {
  const g = new graphlib.Graph();
  g.setGraph({ rankdir: "TB", ranksep: 70, nodesep: 24 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const node of nodes) {
    const isDeprecated = node.pool_status === "deprecated";
    const w = isDeprecated ? DEPRECATED_W : node.kind === "foundation" ? FOUNDATION_W : INTEREST_W;
    const h = isDeprecated ? DEPRECATED_H : node.kind === "foundation" ? FOUNDATION_H : INTEREST_H;
    g.setNode(node.id, { width: w, height: h });
  }

  for (const edge of edges) {
    if (g.node(edge.source_node_id) && g.node(edge.target_node_id)) {
      g.setEdge(edge.source_node_id, edge.target_node_id);
    }
  }

  dagreLayout(g);

  const rfNodes: RFNode[] = nodes.map((node) => {
    const isDeprecated = node.pool_status === "deprecated";
    const w = isDeprecated ? DEPRECATED_W : node.kind === "foundation" ? FOUNDATION_W : INTEREST_W;
    const h = isDeprecated ? DEPRECATED_H : node.kind === "foundation" ? FOUNDATION_H : INTEREST_H;
    const pos = g.node(node.id) ?? { x: 0, y: 0 };
    const type = isDeprecated ? "deprecated" : node.kind;
    return {
      id: node.id,
      type,
      position: { x: pos.x - w / 2, y: pos.y - h / 2 },
      style: { width: w, height: h },
      data: { node, hasProposal: proposalNodeIds.has(node.id) },
    };
  });

  const nodeIds = new Set(nodes.map((n) => n.id));
  const rfEdges: RFEdge[] = edges
    .filter((e) => nodeIds.has(e.source_node_id) && nodeIds.has(e.target_node_id))
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
// Node detail panel
// ---------------------------------------------------------------------------

function NodePanel({
  node,
  proposals,
  onClose,
}: {
  node: MegaNode;
  proposals: CurationProposal[];
  onClose: () => void;
}) {
  const affecting = proposals.filter((p) => {
    const pj = p.payload_json;
    return (
      pj.node_id === node.id ||
      pj.source_node_id === node.id ||
      pj.target_node_id === node.id
    );
  });

  return (
    <div className="absolute right-4 top-4 z-20 w-72 rounded-md border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between">
        <h3 className="font-serif text-sm font-semibold text-foreground">{node.title}</h3>
        <button
          onClick={onClose}
          className="ml-2 text-xs text-muted-foreground hover:text-foreground"
        >
          ✕
        </button>
      </div>
      <dl className="space-y-1 text-xs text-muted-foreground">
        <div>
          <dt className="inline font-medium">Slug: </dt>
          <dd className="inline font-mono">{node.slug}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Kind: </dt>
          <dd className="inline">{node.kind}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Domain: </dt>
          <dd className="inline">{node.domain}</dd>
        </div>
        <div>
          <dt className="inline font-medium">Status: </dt>
          <dd className="inline">{node.pool_status}</dd>
        </div>
      </dl>
      {affecting.length > 0 && (
        <div className="mt-3">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Pending proposals
          </p>
          <ul className="space-y-1">
            {affecting.map((p) => (
              <li key={p.id} className="text-xs text-amber">
                {p.kind}: {p.payload_json.rationale ?? ""}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter sidebar
// ---------------------------------------------------------------------------

const FILTER_DEFS = [
  { key: "foundation", label: "Foundation", defaultOn: true },
  { key: "interest", label: "Interest", defaultOn: true },
  { key: "math", label: "Math", defaultOn: true },
  { key: "physics", label: "Physics", defaultOn: true },
  { key: "applied", label: "Applied", defaultOn: true },
  { key: "deprecated", label: "Deprecated", defaultOn: false },
  { key: "proposals", label: "Show proposals", defaultOn: false },
] as const;

type FilterKey = (typeof FILTER_DEFS)[number]["key"];

function nodePassesFilters(node: MegaNode, filters: Set<FilterKey>): boolean {
  if (node.pool_status === "deprecated" && !filters.has("deprecated")) return false;
  if (node.kind === "foundation" && !filters.has("foundation")) return false;
  if (node.kind === "interest" && !filters.has("interest")) return false;
  if (!filters.has(node.domain as FilterKey)) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

export default function MegagraphPage() {
  const [data, setData] = useState<AdminMegagraphData | null>(null);
  const [rfNodes, setNodes, onNodesChange] = useNodesState<RFNode>([]);
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState<RFEdge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [filters, setFilters] = useState<Set<FilterKey>>(
    () => new Set(FILTER_DEFS.filter((f) => f.defaultOn).map((f) => f.key)),
  );
  const [scrubberPos, setScrubberPos] = useState<number[]>([0]);
  const [scrubberLabel, setScrubberLabel] = useState<string>("Current live state");
  const [takingSnapshot, setTakingSnapshot] = useState(false);

  // Fetch initial data.
  useEffect(() => {
    fetch("/api/admin/megagraph")
      .then((r) => r.json())
      .then((d: AdminMegagraphData) => {
        setData(d);
        // Set scrubber to rightmost (live state).
        setScrubberPos([d.snapshots.length]);
        setScrubberLabel("Current live state");
      })
      .catch(console.error);
  }, []);

  // Rebuild layout when data or filters change.
  useEffect(() => {
    if (!data) return;
    const proposalNodeIds = new Set<string>();
    if (filters.has("proposals")) {
      for (const p of data.pending_proposals) {
        const pj = p.payload_json;
        if (pj.node_id) proposalNodeIds.add(pj.node_id);
        if (pj.source_node_id) proposalNodeIds.add(pj.source_node_id);
        if (pj.target_node_id) proposalNodeIds.add(pj.target_node_id);
      }
    }
    const filteredNodes = data.nodes.filter((n) => nodePassesFilters(n, filters));
    const { nodes: built, edges: builtEdges } = buildLayout(
      filteredNodes,
      data.edges,
      proposalNodeIds,
    );
    setNodes(built);
    setEdges(builtEdges);
  }, [data, filters, setNodes, setEdges]);

  const onNodeClick = useCallback((_event: React.MouseEvent, node: RFNode) => {
    setSelectedNodeId(node.id);
  }, []);

  const onPaneClick = useCallback(() => setSelectedNodeId(null), []);

  function toggleFilter(key: FilterKey) {
    setFilters((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleScrubberChange(val: number[]) {
    const pos = val[0];
    setScrubberPos(val);
    if (!data) return;
    if (pos === data.snapshots.length) {
      // Rightmost = live state.
      setScrubberLabel("Current live state");
      // Reset to live data.
      const filteredNodes = data.nodes.filter((n) => nodePassesFilters(n, filters));
      const { nodes: built, edges: builtEdges } = buildLayout(
        filteredNodes,
        data.edges,
        new Set(),
      );
      setNodes(built);
      setEdges(builtEdges);
      return;
    }
    const snap = data.snapshots[pos];
    if (!snap) return;
    setScrubberLabel(`${snap.label} · ${new Date(snap.taken_at).toLocaleDateString()}`);
    try {
      const res = await fetch(`/api/admin/megagraph/snapshot/${snap.id}`);
      const snapData = await res.json() as { snapshot_json: SnapshotJson };
      const sj = snapData.snapshot_json;
      const snapNodes = (sj?.nodes ?? []) as MegaNode[];
      const snapEdges = (sj?.edges ?? []) as MegaEdge[];
      const filteredNodes = snapNodes.filter((n) => nodePassesFilters(n, filters));
      const { nodes: built, edges: builtEdges } = buildLayout(filteredNodes, snapEdges, new Set());
      setNodes(built);
      setEdges(builtEdges);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleTakeSnapshot() {
    setTakingSnapshot(true);
    try {
      const res = await fetch("/api/admin/megagraph/snapshot", { method: "POST" });
      const snap = await res.json() as Snapshot;
      setData((prev) =>
        prev
          ? {
              ...prev,
              snapshots: [...prev.snapshots, snap],
            }
          : prev,
      );
      // Advance scrubber to the new snapshot.
      if (data) {
        const newPos = data.snapshots.length + 1;
        setScrubberPos([newPos]);
        setScrubberLabel(`${snap.label} · ${new Date(snap.taken_at).toLocaleDateString()}`);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setTakingSnapshot(false);
    }
  }

  const selectedNode = selectedNodeId
    ? data?.nodes.find((n) => n.id === selectedNodeId) ?? null
    : null;

  const snapshotCount = data?.snapshots.length ?? 0;
  const hasSnapshots = snapshotCount > 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between border-b border-border bg-background px-4 py-2">
        <span className="text-sm font-medium text-foreground">
          Megagraph — {data?.nodes.length ?? "…"} nodes
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleTakeSnapshot}
          disabled={takingSnapshot}
        >
          {takingSnapshot ? "Taking…" : "Take snapshot"}
        </Button>
      </div>

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar filters */}
        <div className="w-44 flex-shrink-0 overflow-y-auto border-r border-border bg-background p-4">
          <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Filters
          </p>
          <div className="flex flex-col gap-2.5">
            {FILTER_DEFS.map(({ key, label }) => (
              <div key={key} className="flex items-center gap-2">
                <Checkbox
                  id={`filter-${key}`}
                  checked={filters.has(key)}
                  onCheckedChange={() => toggleFilter(key)}
                />
                <Label htmlFor={`filter-${key}`} className="text-xs text-muted-foreground cursor-pointer">
                  {label}
                </Label>
              </div>
            ))}
          </div>
        </div>

        {/* Canvas */}
        <div className="relative flex-1">
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
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

          {selectedNode && (
            <NodePanel
              node={selectedNode}
              proposals={data?.pending_proposals ?? []}
              onClose={() => setSelectedNodeId(null)}
            />
          )}
        </div>
      </div>

      {/* Time scrubber */}
      <div className="border-t border-border bg-background px-6 py-3">
        <div className="flex items-center gap-4">
          <Slider
            min={0}
            max={Math.max(snapshotCount, 1)}
            step={1}
            value={scrubberPos}
            onValueChange={handleScrubberChange}
            disabled={!hasSnapshots}
            className="flex-1"
          />
          <span className="w-64 flex-shrink-0 text-right text-xs text-muted-foreground">
            {hasSnapshots
              ? scrubberLabel
              : "No snapshots yet — run curation to create the first."}
          </span>
        </div>
      </div>
    </div>
  );
}
