"use client";

// Concept tour for one resolved interest — survey-and-difficulty-design.md §1.6.
//
// Renders 6–10 subtopic tiles drawn from the resolved interest's prerequisite
// foundation nodes. Each tile has three-state self-report:
//   Familiar       → user_node_states.state = 'comfortable'
//   Want a refresh → user_node_states.state = 'active'
//   New to me      → user_node_states.state = 'unseen' (explicit)
//   Unclicked      → 'unseen' (implicit, not posted)
//
// On submit we POST one bulk write to /api/add-interest/concept-tour which
// writes user_node_states and appends to surveys.comfort_responses_json.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { ConceptTourTileDTO } from "@/lib/pythonApi";

export type ConceptTourState = "familiar" | "refresh" | "new";

interface Props {
  // The resolved interest's name — shown in the headline.
  interestTitle: string;
  // 6–10 subtopic tiles from /resolve.
  tiles: ConceptTourTileDTO[];
  // Node-scoped keys ("<node_id>:<subtopic_key>") for tiles the user actually
  // answered in an earlier tour this session — these are filtered out (§1.6.5).
  seenSubtopicKeys: Set<string>;
  // Show the "Skip remaining tours" affordance — orchestrator passes true
  // after the second tour.
  showSkipRemaining?: boolean;
  onSubmit: (args: {
    addressed: Array<{
      nodeId: string;
      subtopicKey: string;
      state: ConceptTourState;
    }>;
    skippedAll: boolean;
    skipRemaining: boolean;
  }) => void | Promise<void>;
}

const STATE_LABELS: Record<ConceptTourState, string> = {
  familiar: "Familiar",
  refresh: "Refresh",
  new: "New to me",
};

export default function ConceptTour({
  interestTitle,
  tiles,
  seenSubtopicKeys,
  showSkipRemaining = false,
  onSubmit,
}: Props) {
  const visibleTiles = tiles.filter(
    (t) => !seenSubtopicKeys.has(`${t.node_id}:${t.subtopic_key}`),
  );
  const [picks, setPicks] = useState<Record<string, ConceptTourState>>({});
  const [submitting, setSubmitting] = useState(false);

  function setState(subtopicKey: string, state: ConceptTourState) {
    setPicks((prev) => {
      const next = { ...prev };
      if (next[subtopicKey] === state) {
        delete next[subtopicKey]; // tap again to clear
      } else {
        next[subtopicKey] = state;
      }
      return next;
    });
  }

  async function finish(skip: { all: boolean; remaining: boolean }) {
    setSubmitting(true);
    try {
      const addressed = visibleTiles
        .filter((t) => picks[t.subtopic_key])
        .map((t) => ({
          nodeId: t.node_id,
          subtopicKey: t.subtopic_key,
          state: picks[t.subtopic_key],
        }));
      await onSubmit({
        addressed,
        skippedAll: skip.all,
        skipRemaining: skip.remaining,
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (visibleTiles.length === 0) {
    // Everything was covered in an earlier tour — let the orchestrator move on.
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <p className="font-serif text-base text-foreground">
          We&apos;ve already covered the prerequisites for {interestTitle} earlier.
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
        First, the groundwork {interestTitle} builds on.
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        These are the foundations {interestTitle} leans on — not the topic
        itself. Mark anything you already know or want to revisit, and leave the
        rest. It just helps us judge where to start; it&apos;s not a test, and
        nothing here is required.
      </p>

      <div className="mt-6 flex flex-col gap-3">
        {visibleTiles.map((tile) => {
          const picked = picks[tile.subtopic_key];
          return (
            <div
              key={`${tile.node_id}:${tile.subtopic_key}`}
              className="flex flex-col gap-2 rounded-md border border-border bg-card p-4"
            >
              <div className="flex flex-col gap-1">
                <p className="font-serif text-base text-foreground">{tile.name}</p>
                {tile.gloss && (
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    {tile.gloss}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {(["familiar", "refresh", "new"] as ConceptTourState[]).map((s) => {
                  const active = picked === s;
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setState(tile.subtopic_key, s)}
                      className={`rounded-md border px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors duration-[var(--duration-fast)] ${
                        active
                          ? s === "familiar"
                            ? "border-[var(--forest)]/50 bg-[var(--forest-subtle)] text-foreground"
                            : s === "refresh"
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
            Skip this tour
          </Button>
          {showSkipRemaining && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => finish({ all: true, remaining: true })}
              disabled={submitting}
            >
              Skip remaining tours
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
