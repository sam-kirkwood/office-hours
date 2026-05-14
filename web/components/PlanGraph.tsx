"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import SkillTreeView from "./SkillTreeView";
import type { NodeVariant } from "./SkillTree";
import type { PlanNode, CanonicalTopic, CanonicalEdge } from "@/lib/types";

interface PlanGraphProps {
  planId: string;
  planNodes: PlanNode[];
  allTopics: CanonicalTopic[];
  allEdges: CanonicalEdge[];
}

export default function PlanGraph({ planNodes, allTopics, allEdges }: PlanGraphProps) {
  const router = useRouter();
  const [adjusting, setAdjusting] = useState(false);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  const variants = useMemo<Record<string, NodeVariant>>(() => {
    const v: Record<string, NodeVariant> = {};
    for (const node of planNodes) {
      v[node.canonical_topic_id] = node.state === "mastered" ? "mastered" : "in-plan";
    }
    return v;
  }, [planNodes]);

  const handleApprove = async () => {
    setLoading(true);
    const res = await fetch("/api/plan/approve", { method: "POST" });
    if (res.ok) {
      router.push("/daily");
    } else {
      setLoading(false);
    }
  };

  const handleAdjust = async () => {
    setLoading(true);
    const res = await fetch("/api/plan/adjust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    });
    setLoading(false);
    if (res.ok) {
      setNotes("");
      setAdjusting(false);
      router.refresh();
    }
  };

  const planCount = planNodes.length;
  const masteredCount = planNodes.filter((n) => n.state === "mastered").length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 p-4 bg-zinc-50 rounded-lg border border-zinc-200">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <p className="text-sm text-zinc-600">
            <span className="font-semibold text-zinc-900">{planCount}</span> topics in your
            plan
            {masteredCount > 0 && (
              <span className="text-zinc-500">
                {" "}
                ({masteredCount} already known)
              </span>
            )}
          </p>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setAdjusting((a) => !a)}
              disabled={loading}
              className="px-4 py-2 border border-zinc-300 text-zinc-700 text-sm font-medium rounded hover:bg-zinc-100 disabled:opacity-50 transition-colors"
            >
              {adjusting ? "Cancel" : "Request changes"}
            </button>
            <button
              onClick={handleApprove}
              disabled={loading}
              className="px-4 py-2 bg-zinc-900 text-white text-sm font-medium rounded hover:bg-zinc-700 disabled:opacity-50 transition-colors"
            >
              Approve & start
            </button>
          </div>
        </div>
        {adjusting && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-zinc-500">
              Describe any changes. Notes are saved and will be used when AI-assisted
              re-planning is available.
            </p>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. I want to focus more on electromagnetism and skip statistics"
              className="w-full p-2 text-sm border border-zinc-300 rounded resize-none h-20 focus:outline-none focus:ring-1 focus:ring-zinc-400"
            />
            <button
              onClick={handleAdjust}
              disabled={loading || !notes.trim()}
              className="self-start px-4 py-2 bg-zinc-900 text-white text-sm font-medium rounded hover:bg-zinc-700 disabled:opacity-50 transition-colors"
            >
              Re-generate
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-4 text-xs text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded border-2 border-zinc-900 bg-zinc-900 inline-block" />
          In plan
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded border-2 border-emerald-300 bg-emerald-50 inline-block" />
          Already known
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded border-2 border-zinc-400 bg-white inline-block" />
          Context (not in plan)
        </span>
      </div>

      <SkillTreeView topics={allTopics} edges={allEdges} variants={variants} />
    </div>
  );
}
