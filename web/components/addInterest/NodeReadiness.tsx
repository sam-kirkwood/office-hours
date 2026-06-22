"use client";

// Node-level readiness pass — orientation-and-calibration-design.md §B1/§B3
// (Phase 13 Step 3). Replaces the subtopic ConceptTour with a coarse,
// node-level read over the prerequisite NODES the interest leans on.
//
// Each tile is one prerequisite node with three-state self-report:
//   Solid → user_node_states.state = 'comfortable'
//   Rusty → 'active'
//   New   → 'unseen'
//   Unclicked → not posted (left unspecified)
//
// On submit we POST one write to /api/add-interest/node-readiness, which maps
// the labels to DB states and upserts node-level user_node_states. Subtopic
// detail is no longer cold-collected — it accrues from engagement + the node
// panel (§B1).

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { NodeReadinessTileDTO, NodeReadinessState } from "@/lib/pythonApi";

interface Props {
  // The resolved interest's name — shown in the headline.
  interestTitle: string;
  // The prerequisite-node tiles from /resolve.
  tiles: NodeReadinessTileDTO[];
  // Node ids already answered in an earlier pass this session — filtered out.
  seenNodeIds: Set<string>;
  // Show the "Skip remaining" affordance — orchestrator passes true after the
  // second pass.
  showSkipRemaining?: boolean;
  onSubmit: (args: {
    nodeStates: Array<{ nodeId: string; state: NodeReadinessState }>;
    skippedAll: boolean;
    skipRemaining: boolean;
  }) => void | Promise<void>;
}

const STATE_LABELS: Record<NodeReadinessState, string> = {
  solid: "Solid",
  rusty: "Rusty",
  new: "New to me",
};

export default function NodeReadiness({
  interestTitle,
  tiles,
  seenNodeIds,
  showSkipRemaining = false,
  onSubmit,
}: Props) {
  const visibleTiles = tiles.filter((t) => !seenNodeIds.has(t.node_id));
  const [picks, setPicks] = useState<Record<string, NodeReadinessState>>({});
  const [submitting, setSubmitting] = useState(false);

  function setState(nodeId: string, state: NodeReadinessState) {
    setPicks((prev) => {
      const next = { ...prev };
      if (next[nodeId] === state) {
        delete next[nodeId]; // tap again to clear
      } else {
        next[nodeId] = state;
      }
      return next;
    });
  }

  async function finish(skip: { all: boolean; remaining: boolean }) {
    setSubmitting(true);
    try {
      const nodeStates = visibleTiles
        .filter((t) => picks[t.node_id])
        .map((t) => ({ nodeId: t.node_id, state: picks[t.node_id] }));
      await onSubmit({
        nodeStates,
        skippedAll: skip.all,
        skipRemaining: skip.remaining,
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (visibleTiles.length === 0) {
    // Everything was covered in an earlier pass — let the orchestrator move on.
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <p className="font-serif text-base text-foreground">
          We&apos;ve already covered what {interestTitle} builds on.
        </p>
        <div className="mt-6 flex justify-end">
          <Button
            type="button"
            onClick={() => finish({ all: false, remaining: false })}
            disabled={submitting}
            size="lg"
          >
            Continue →
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-5 py-10">
      <h2 className="font-serif text-xl text-foreground">
        What {interestTitle} builds on.
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        These are the areas {interestTitle} leans on. Tell us roughly where you
        stand on each — solid, rusty, or new — and leave the rest. It just helps
        us judge where to start; it&apos;s not a test, and nothing here is
        required.
      </p>

      <div className="mt-6 flex flex-col gap-3">
        {visibleTiles.map((tile) => {
          const picked = picks[tile.node_id];
          return (
            <div
              key={tile.node_id}
              className="flex flex-col gap-2 rounded-md border border-border bg-card p-4"
            >
              <div className="flex flex-col gap-1">
                <p className="font-serif text-base text-foreground">
                  {tile.node_title}
                </p>
                {tile.node_description_preview && (
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {tile.node_description_preview}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {(["solid", "rusty", "new"] as NodeReadinessState[]).map((s) => {
                  const active = picked === s;
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setState(tile.node_id, s)}
                      className={`rounded-md border px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors duration-[var(--duration-fast)] ${
                        active
                          ? s === "solid"
                            ? "border-[var(--forest)]/50 bg-[var(--forest-subtle)] text-foreground"
                            : s === "rusty"
                              ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                              : "border-border bg-muted text-foreground"
                          : "border-border bg-background text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                      }`}
                    >
                      {STATE_LABELS[s]}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-3">
          <Button
            type="button"
            variant="ghost"
            onClick={() => finish({ all: true, remaining: false })}
            disabled={submitting}
          >
            Skip this
          </Button>
          {showSkipRemaining && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => finish({ all: true, remaining: true })}
              disabled={submitting}
            >
              Skip remaining
            </Button>
          )}
        </div>
        <Button
          type="button"
          onClick={() => finish({ all: false, remaining: false })}
          disabled={submitting}
          size="lg"
        >
          {submitting ? "Saving…" : "Continue →"}
        </Button>
      </div>
    </div>
  );
}
