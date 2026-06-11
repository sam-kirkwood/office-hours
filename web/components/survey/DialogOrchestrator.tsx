"use client";

// Stage 4 + 5 orchestrator (survey-and-difficulty-design.md §1.5–§1.6).
//
// Walks the user through:
//   for each raw_text input (selected tile titles + free text from Stage 3):
//     call /api/add-interest/parse → segments[]
//     for each segment:
//       1. Render Dialog (mirror back, optional followup or path pick, resolve)
//       2. On resolved: render ConceptTour for the resolved interest
//          (skippable; dedups tiles against prior tours this session)
//   finalise: clear pending_interests_json, mark `dialog` stage done,
//   navigate to /survey/balance.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import Dialog from "@/components/addInterest/Dialog";
import ConceptTour, {
  type ConceptTourState,
} from "@/components/addInterest/ConceptTour";
import type { DialogResolved } from "@/components/addInterest/types";
import type {
  ParsedInterestSegmentDTO,
  ConceptTourTileDTO,
} from "@/lib/pythonApi";

interface Props {
  inputs: string[];
}

type Phase =
  | "parsing"
  | "dialog"
  | "starter"
  | "tour"
  | "completing"
  | "done"
  | "error"
  | "empty";

interface ResolvedItem {
  result: DialogResolved;
  tiles: ConceptTourTileDTO[];
  interestTitle: string;
}

export default function DialogOrchestrator({ inputs }: Props) {
  const router = useRouter();

  const [inputIdx, setInputIdx] = useState(0);
  const [segments, setSegments] = useState<ParsedInterestSegmentDTO[]>([]);
  const [segmentIdx, setSegmentIdx] = useState(0);

  const [resolved, setResolved] = useState<ResolvedItem | null>(null);
  const [seenSubtopicKeys, setSeenSubtopicKeys] = useState<Set<string>>(new Set());
  const [completedTourCount, setCompletedTourCount] = useState(0);
  const [skipAllRemainingTours, setSkipAllRemainingTours] = useState(false);
  const [resolvedSummaries, setResolvedSummaries] = useState<string[]>([]);

  const [phase, setPhase] = useState<Phase>(inputs.length === 0 ? "empty" : "parsing");
  const [error, setError] = useState<string | null>(null);

  const currentInput = inputs[inputIdx];

  // Drive /parse whenever we land on a new input.
  useEffect(() => {
    if (phase !== "parsing") return;
    if (!currentInput) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/add-interest/parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ raw_text: currentInput, added_via: "survey" }),
        });
        if (!res.ok) {
          const j = await res.json().catch(() => ({}));
          throw new Error((j as { error?: string }).error ?? "Parse failed");
        }
        const data = (await res.json()) as { segments: ParsedInterestSegmentDTO[] };
        if (cancelled) return;
        if (data.segments.length === 0) {
          // Move past this input silently.
          advanceInput();
          return;
        }
        setSegments(data.segments);
        setSegmentIdx(0);
        setPhase("dialog");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Parse failed");
        setPhase("error");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, currentInput]);

  function advanceInput() {
    const nextIdx = inputIdx + 1;
    if (nextIdx >= inputs.length) {
      finish();
    } else {
      setInputIdx(nextIdx);
      setSegments([]);
      setSegmentIdx(0);
      setPhase("parsing");
    }
  }

  function advanceSegment() {
    const nextSegIdx = segmentIdx + 1;
    if (nextSegIdx < segments.length) {
      setSegmentIdx(nextSegIdx);
      setPhase("dialog");
    } else {
      advanceInput();
    }
  }

  async function finish() {
    setPhase("completing");
    try {
      const res = await fetch("/api/survey/dialog/complete", { method: "POST" });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error((j as { error?: string }).error ?? "Save failed");
      }
      router.push("/survey/balance");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setPhase("error");
    }
  }

  function handleResolved(result: DialogResolved) {
    const seg = segments[segmentIdx];
    setResolved({
      result,
      tiles: result.concept_tour,
      interestTitle: seg?.raw_text_segment || currentInput,
    });
    setResolvedSummaries((prev) => [
      ...prev,
      `${seg?.raw_text_segment || currentInput} → ${result.intent_context}`,
    ]);
    setPhase("starter");
  }

  async function handleTourSubmit(args: {
    addressed: Array<{
      nodeId: string;
      subtopicKey: string;
      state: ConceptTourState;
    }>;
    skippedAll: boolean;
    skipRemaining: boolean;
  }) {
    try {
      const res = await fetch("/api/add-interest/concept-tour", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          addressed: args.addressed.map((a) => ({
            // node_id is already in DTO; orchestrator passes it through.
            node_id: a.nodeId,
            // Look up node_slug from the tour tiles for the comfort_responses_json key.
            node_slug:
              resolved?.tiles.find(
                (t) =>
                  t.node_id === a.nodeId && t.subtopic_key === a.subtopicKey,
              )?.node_slug ?? "",
            subtopic_key: a.subtopicKey,
            state: a.state,
          })),
          for_interest_node_slug: resolved?.result.node_slug,
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        console.error("concept-tour write failed:", j);
      }
    } catch (err) {
      console.error("concept-tour write failed:", err);
    }

    // Whether or not the network write succeeded, advance — onboarding should
    // not be blocked on telemetry.
    setCompletedTourCount((n) => n + 1);
    if (args.skipRemaining) setSkipAllRemainingTours(true);

    // Merge the tiles the user actually answered into the seen set so
    // subsequent tours dedup them out. Per survey-and-difficulty-design.md
    // §1.6.5 a tile is only "covered" when its state was captured — tiles the
    // user left unanswered must reappear in later tours, not be silently
    // hidden. Keys are node-scoped (node_id:subtopic_key) so the same subtopic
    // name under a different foundation node isn't wrongly suppressed.
    if (args.addressed.length > 0) {
      setSeenSubtopicKeys((prev) => {
        const next = new Set(prev);
        for (const a of args.addressed) next.add(`${a.nodeId}:${a.subtopicKey}`);
        return next;
      });
    }

    setResolved(null);
    advanceSegment();
  }

  // Empty path: no inputs at all. Should be uncommon (Stage 3 requires at
  // least one), but skip cleanly to balance.
  if (phase === "empty") {
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <p className="font-serif text-lg text-foreground">
          Nothing to settle yet — moving on.
        </p>
        <div className="mt-6 flex justify-end">
          <Button type="button" size="lg" onClick={finish}>
            Continue →
          </Button>
        </div>
      </div>
    );
  }

  if (phase === "parsing" || phase === "completing") {
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <p className="font-serif text-base text-muted-foreground">
          {phase === "completing" ? "Settling in…" : "Reading what you said…"}
        </p>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <p className="font-serif text-lg text-foreground">Something went wrong.</p>
        <p className="mt-2 text-sm text-destructive">{error}</p>
        <div className="mt-6 flex gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setError(null);
              setPhase("parsing");
            }}
          >
            Try again
          </Button>
          <Button type="button" variant="ghost" onClick={advanceInput}>
            Skip this one
          </Button>
        </div>
      </div>
    );
  }

  if (phase === "dialog") {
    const seg = segments[segmentIdx];
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <OrchestratorProgress
          inputIdx={inputIdx}
          totalInputs={inputs.length}
          segmentIdx={segmentIdx}
          totalSegments={segments.length}
        />
        <Dialog
          rawText={currentInput}
          input={{ source: "segment", segment: seg }}
          addedVia="survey"
          presentation="full-page"
          onResolved={handleResolved}
        />
      </div>
    );
  }

  if (phase === "starter" && resolved) {
    return (
      <div className="mx-auto max-w-2xl px-5 py-10">
        <p className="font-serif text-lg leading-[1.7] text-foreground">
          {resolved.result.starter_preview_md}
        </p>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Before we go further: a quick lay of the land, so we know where to start.
        </p>
        <div className="mt-6 flex justify-end">
          <Button
            type="button"
            size="lg"
            onClick={() => {
              if (skipAllRemainingTours) {
                setResolved(null);
                advanceSegment();
              } else {
                setPhase("tour");
              }
            }}
          >
            {skipAllRemainingTours ? "Continue →" : "Show me →"}
          </Button>
        </div>
      </div>
    );
  }

  if (phase === "tour" && resolved) {
    return (
      <ConceptTour
        interestTitle={resolved.interestTitle}
        tiles={resolved.tiles}
        seenSubtopicKeys={seenSubtopicKeys}
        showSkipRemaining={completedTourCount >= 1 /* surface after the 2nd tour starts */}
        onSubmit={handleTourSubmit}
      />
    );
  }

  return null;
}

function OrchestratorProgress({
  inputIdx,
  totalInputs,
  segmentIdx,
  totalSegments,
}: {
  inputIdx: number;
  totalInputs: number;
  segmentIdx: number;
  totalSegments: number;
}) {
  if (totalInputs <= 1 && totalSegments <= 1) return null;
  return (
    <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
      Interest {inputIdx + 1} of {totalInputs}
      {totalSegments > 1 ? ` · part ${segmentIdx + 1} of ${totalSegments}` : ""}
    </p>
  );
}
