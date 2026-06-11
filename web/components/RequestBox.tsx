"use client";

// Daily-tab "Curious about something specific?" entry point.
// survey-and-difficulty-design.md §2.7 — three cases:
//
//   Case 1 (new topic): segment.kind === "interest" and the matched node
//     (if any) is not already in user_interests. Show a small modal asking
//     "Add it" vs "Just this once"; "Add it" opens the full add-interest
//     dialog, "Just this once" queues a problem on the matched node without
//     persisting the interest. If there is no match (dedup verdict='new' or
//     'related'), only "Add it" is available — we have to commit to create
//     a new node.
//
//   Case 2 (existing topic, one-off): segment matched an existing user_interests
//     entry. Queue directly, no dialog.
//
//   Case 3 (concept / subtopic): segment.kind === "concept". Queue a focused
//     problem on the matched topic if any; no node creation, no interest add.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import DialogModal from "@/components/addInterest/DialogModal";
import { optimisticQueueRequest, queueItemPath } from "@/lib/optimisticQueueRequest";
import type { ParsedInterestSegmentDTO } from "@/lib/pythonApi";

type KindHint = "problem" | "paper" | "refresher";

type RouteDecision =
  | { case: "case1-with-match"; segment: ParsedInterestSegmentDTO; matchedNodeId: string }
  | { case: "case1-no-match"; segment: ParsedInterestSegmentDTO }
  | { case: "case2-existing"; matchedNodeId: string }
  | { case: "case3-concept"; matchedNodeId: string | null };

interface InterestHasResponse {
  exists: boolean;
}

export default function RequestBox() {
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState("");
  const [kindHint, setKindHint] = useState<KindHint>("problem");
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState<RouteDecision | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const router = useRouter();

  function reset() {
    setText("");
    setPending(null);
    setError(null);
  }

  function queueProblemOnNode(nodeId: string, skipInterestAdd: boolean) {
    // Fire-and-forget: optimisticQueueRequest carries success/error via toast.
    optimisticQueueRequest({
      body: {
        node_id: nodeId,
        kind_hint: "problem",
        skip_interest_add: skipInterestAdd,
      },
      targetPath: (id) => `/problem/${id}`,
      router,
      labels: {
        pending: "Finding a problem…",
        queued: "Added to your queue.",
      },
    }).catch(() => {/* surfaced via toast */});
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const rawText = text.trim();
    if (!rawText) return;
    setParsing(true);
    setError(null);
    setMessage(null);

    try {
      // Paper / refresher kinds don't go through the add-interest dialog —
      // fire-and-forget via the shared helper (phase-10-rev §Step 4 #39).
      if (kindHint !== "problem") {
        const pendingLabel =
          kindHint === "paper" ? "Finding a paper…" : "Lining up a refresher…";
        const queuedLabel =
          kindHint === "paper"
            ? "Adding a paper to your queue — it'll appear shortly."
            : "Refresher added to your queue.";
        optimisticQueueRequest({
          body: { raw_text: rawText, kind_hint: kindHint },
          // Paper requests always land on /paper; refreshers resolve to a
          // concrete kind (problem / concept_review / paper_engagement).
          targetPath: kindHint === "paper" ? (id) => `/paper/${id}` : queueItemPath,
          router,
          labels: { pending: pendingLabel, queued: queuedLabel },
        }).catch(() => {/* surfaced via toast */});
        setText("");
        return;
      }

      // Problem kind → run through /parse to detect §2.7 case.
      const parseRes = await fetch("/api/add-interest/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText, added_via: "explicit_request" }),
      });
      const parseData = (await parseRes.json()) as
        | { segments: ParsedInterestSegmentDTO[] }
        | { error: string };
      if (!parseRes.ok) {
        throw new Error((parseData as { error?: string }).error ?? "Parse failed");
      }
      const segments = (parseData as { segments: ParsedInterestSegmentDTO[] }).segments;
      if (segments.length === 0) {
        throw new Error("Couldn't understand that — try a different phrasing?");
      }
      // Daily-tab use case is single-segment; if the user types compound input
      // we walk the first segment only and surface a hint about the rest.
      const seg = segments[0];

      // Resolve matched node id + interest membership in one call.
      const matchedSlug = seg.dedup.matched_node_slug;
      let matchedNodeId: string | null = null;
      let matchedInInterests = false;
      if (matchedSlug) {
        const r = await fetch(
          `/api/interest/me?node_slug=${encodeURIComponent(matchedSlug)}`,
        );
        if (r.ok) {
          const j = (await r.json()) as InterestHasResponse & {
            node_id: string | null;
          };
          matchedInInterests = j.exists;
          matchedNodeId = j.node_id;
        }
      }

      if (seg.kind === "concept") {
        if (matchedNodeId) {
          queueProblemOnNode(matchedNodeId, true);
          setText("");
        } else {
          setMessage(
            "We couldn't tie that to a topic yet — try adding it as an interest.",
          );
        }
        return;
      }

      // kind === "interest"
      if (seg.dedup.verdict === "same" && matchedNodeId && matchedInInterests) {
        // Case 2
        queueProblemOnNode(matchedNodeId, true);
        setText("");
        return;
      }

      // Case 1
      const decision: RouteDecision =
        seg.dedup.verdict === "same" && matchedNodeId
          ? { case: "case1-with-match", segment: seg, matchedNodeId }
          : { case: "case1-no-match", segment: seg };
      setPending(decision);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setParsing(false);
    }
  }

  function handleJustThisOnce() {
    if (!pending || pending.case !== "case1-with-match") return;
    queueProblemOnNode(pending.matchedNodeId, true);
    reset();
  }

  function handleAddIt() {
    setDialogOpen(true);
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)]"
      >
        Curious about something specific? →
      </button>
    );
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-2">
          {(["problem", "paper", "refresher"] as KindHint[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKindHint(k)}
              className={`px-2.5 py-1 rounded text-xs border transition-colors duration-[var(--duration-fast)] ${
                kindHint === k
                  ? "border-[var(--primary)] bg-[var(--amber-subtle)] text-foreground font-medium"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {k.charAt(0).toUpperCase() + k.slice(1)}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              kindHint === "paper"
                ? "e.g. LIGO, neural networks, topology"
                : kindHint === "refresher"
                ? "e.g. contour integration, Fourier series"
                : "Curious about something specific?"
            }
            className="flex-1 rounded border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)] placeholder:text-muted-foreground/60"
          />
          <Button type="submit" size="sm" disabled={parsing || !text.trim()}>
            {parsing ? "…" : "Go →"}
          </Button>
        </div>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </form>

      {pending && (pending.case === "case1-with-match" || pending.case === "case1-no-match") && (
        <div className="mt-4 rounded-md border border-border bg-card p-4">
          <p className="font-serif text-base leading-[1.7] text-foreground">
            {pending.segment.mirror_back_md}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {pending.case === "case1-with-match"
              ? "That isn't in your interests yet — want to add it, or just get one item for now?"
              : "That's new to your interests. Want to add it?"}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" onClick={handleAddIt}>
              Add it
            </Button>
            {pending.case === "case1-with-match" && (
              <Button
                type="button"
                variant="outline"
                onClick={handleJustThisOnce}
                disabled={parsing}
              >
                Just this once
              </Button>
            )}
            <Button type="button" variant="ghost" onClick={reset}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {pending &&
        (pending.case === "case1-with-match" || pending.case === "case1-no-match") && (
          <DialogModal
            open={dialogOpen}
            onOpenChange={(open) => {
              setDialogOpen(open);
              if (!open) {
                reset();
                router.refresh();
              }
            }}
            mode="segment"
            rawText={text}
            segment={pending.segment}
            addedVia="explicit_request"
            title="Add interest"
            onComplete={(r) => {
              queueProblemOnNode(r.node_id, false);
            }}
          />
        )}
    </>
  );
}
