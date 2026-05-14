"use client";

import { useEffect, useMemo } from "react";
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import type { CanonicalTopic, CanonicalEdge } from "@/lib/types";

export type NodeVariant =
  | "target"
  | "known"
  | "refresher"
  | "needed"
  | "in-plan"
  | "mastered"
  | "context";

const NODE_W = 168;
const NODE_H = 56;

function variantClass(variant: NodeVariant, band: string): string {
  const bandBorder =
    band === "intro"
      ? "border-blue-300"
      : band === "advanced"
        ? "border-amber-400"
        : "border-zinc-400";

  switch (variant) {
    case "target":
      return "bg-blue-600 text-white border-blue-700 shadow-md";
    case "known":
      return `bg-emerald-50 text-emerald-700 border-emerald-300`;
    case "refresher":
      return `bg-amber-50 text-amber-800 ${bandBorder} border-dashed`;
    case "needed":
      return `bg-blue-50 text-blue-900 border-blue-300`;
    case "in-plan":
      return "bg-zinc-900 text-white border-zinc-900";
    case "mastered":
      return "bg-emerald-50 text-emerald-700 border-emerald-300 opacity-70";
    case "context":
    default:
      return `bg-white text-zinc-400 ${bandBorder}`;
  }
}

function variantIcon(variant: NodeVariant): string | null {
  switch (variant) {
    case "target":
      return "★";
    case "known":
    case "mastered":
      return "✓";
    case "refresher":
      return "↻";
    default:
      return null;
  }
}

type TopicNodeData = {
  topic: CanonicalTopic;
  variant: NodeVariant;
  clickable: boolean;
};

type TopicNodeType = Node<TopicNodeData, "topic">;

function TopicNode({ data }: NodeProps<TopicNodeType>) {
  const { topic, variant, clickable } = data;
  const klass = variantClass(variant, topic.difficulty_band);
  const icon = variantIcon(variant);
  return (
    <div
      className={`border-2 rounded-md px-3 py-2 text-xs font-medium flex items-center justify-center gap-1.5 text-center leading-tight transition-colors ${klass} ${clickable ? "cursor-pointer hover:brightness-105" : ""}`}
      style={{ width: NODE_W, height: NODE_H }}
    >
      <Handle type="target" position={Position.Left} style={{ background: "#a1a1aa" }} />
      {icon && <span className="text-sm">{icon}</span>}
      <span>{topic.title}</span>
      <Handle type="source" position={Position.Right} style={{ background: "#a1a1aa" }} />
    </div>
  );
}

const nodeTypes = { topic: TopicNode };

function layout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", ranksep: 90, nodesep: 36 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 } };
  });
}

interface SkillTreeProps {
  topics: CanonicalTopic[];
  edges: CanonicalEdge[];
  variants: Record<string, NodeVariant>;
  onNodeClick?: (topicId: string) => void;
  height?: number;
}

export default function SkillTree({
  topics,
  edges,
  variants,
  onNodeClick,
  height = 580,
}: SkillTreeProps) {
  const topicIdSet = useMemo(() => new Set(topics.map((t) => t.id)), [topics]);

  const layoutedNodes = useMemo(
    () =>
      layout(
        topics.map((topic) => ({
          id: topic.id,
          type: "topic",
          position: { x: 0, y: 0 },
          data: {
            topic,
            variant: variants[topic.id] ?? "context",
            clickable: !!onNodeClick,
          } satisfies TopicNodeData,
        })),
        edges
          .filter(
            (e) =>
              topicIdSet.has(e.prerequisite_topic_id) &&
              topicIdSet.has(e.dependent_topic_id)
          )
          .map((e) => ({
            id: e.id,
            source: e.prerequisite_topic_id,
            target: e.dependent_topic_id,
          }))
      ),
    // We want layout to be computed once per topic/edge set — variants update
    // node data via the state setter below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topics, edges]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      edges
        .filter(
          (e) =>
            topicIdSet.has(e.prerequisite_topic_id) &&
            topicIdSet.has(e.dependent_topic_id)
        )
        .map((e) => ({
          id: e.id,
          source: e.prerequisite_topic_id,
          target: e.dependent_topic_id,
          type: "smoothstep",
          style: { stroke: "#d4d4d8" },
        })),
    [edges, topicIdSet]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [rfEdges, , onEdgesChange] = useEdgesState(initialEdges);

  // Push new variants into node data without re-running layout.
  useEffect(() => {
    setNodes((prev) =>
      prev.map((n) => {
        const variant = variants[n.id] ?? "context";
        const existing = n.data as TopicNodeData;
        if (existing.variant === variant) return n;
        return { ...n, data: { ...existing, variant } };
      })
    );
  }, [variants, setNodes]);

  return (
    <div
      className="border border-zinc-200 rounded-lg overflow-hidden bg-white"
      style={{ height }}
    >
      <ReactFlow
        nodes={nodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onNodeClick?.(node.id)}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="#e4e4e7" gap={20} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
