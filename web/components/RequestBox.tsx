"use client";

// Daily-tab curiosity box — classify-and-route (§A4).
//
// For the default (problem) path, input goes through /api/curiosity-box which
// classifies it into one of 9 kinds and returns the lightest sufficient action:
//
//   redirect_steer   → show a message pointing to the steering chips above
//   redirect_feedback → open FeedbackDialog pre-filled with the user's text
//   answer           → brief Haiku answer + follow-on offer
//   queued_pinned    → item queued and pinned (§A6); show link
//   ingest_paper       → call optimisticQueueRequest with kind_hint="paper"
//   topic_new_explored → one-off pinned item queued (no interest added); card offers
//                        "Go to it now →" (primary) + "Add it properly →" (commit opt-in)
//   topic_new_stub     → no node in graph; "Add it properly →" (re-parses + opens dialog)
//   graceful           → warm in-character reply, no machinery
//   clarify            → ask a clarifying question
//
// Paper and refresher kind-hint chips bypass the classifier and go directly to
// the existing optimisticQueueRequest flow (unchanged from before).

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { FeedbackDialog } from "@/components/FeedbackDialog";
import DialogModal from "@/components/addInterest/DialogModal";
import { optimisticQueueRequest, queueItemPath } from "@/lib/optimisticQueueRequest";
import type { CuriosityBoxResponse } from "@/lib/pythonApi";
import type { ParsedInterestSegmentDTO } from "@/lib/pythonApi";

type KindHint = "problem" | "paper" | "refresher";

// Segment pending state — only used when topic_new_stub "Add it" triggers a
// re-parse that yields a segment for the add-interest dialog.
type SegmentPending =
  | { case: "case1-with-match"; segment: ParsedInterestSegmentDTO; matchedNodeId: string }
  | { case: "case1-no-match"; segment: ParsedInterestSegmentDTO };

interface InterestHasResponse {
  exists: boolean;
  node_id: string | null;
}

export default function RequestBox() {
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState("");
  const [kindHint, setKindHint] = useState<KindHint>("problem");
  const [classifying, setClassifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Result of a successful classify call.
  const [curiosityResult, setCuriosityResult] = useState<CuriosityBoxResponse | null>(null);

  // State for feedback-redirect controlled dialog.
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  // State for topic_new_explored / topic_new_stub → "Add it properly" → DialogModal path.
  const [segmentPending, setSegmentPending] = useState<SegmentPending | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reParsing, setReParsing] = useState(false);

  const router = useRouter();

  function reset() {
    setText("");
    setCuriosityResult(null);
    setSegmentPending(null);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const rawText = text.trim();
    if (!rawText) return;
    setClassifying(true);
    setError(null);
    setCuriosityResult(null);

    try {
      // Paper / refresher kind-hint chips bypass the classifier entirely.
      if (kindHint !== "problem") {
        const pendingLabel =
          kindHint === "paper" ? "Finding a paper…" : "Lining up a refresher…";
        const queuedLabel =
          kindHint === "paper"
            ? "Adding a paper to your queue — it'll appear shortly."
            : "Refresher added to your queue.";
        optimisticQueueRequest({
          body: { raw_text: rawText, kind_hint: kindHint },
          targetPath: kindHint === "paper" ? (id) => `/paper/${id}` : queueItemPath,
          router,
          labels: { pending: pendingLabel, queued: queuedLabel },
        }).catch(() => {/* surfaced via toast */});
        setText("");
        return;
      }

      // Problem path → classify-and-route.
      const res = await fetch("/api/curiosity-box", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText }),
      });
      const data = (await res.json()) as CuriosityBoxResponse & { error?: string };
      if (!res.ok) throw new Error(data.error ?? "Classification failed");

      // For ingest_paper, fire the existing paper-request flow immediately and
      // show a result card confirming it's on its way.
      if (data.action === "ingest_paper" && data.paper_ref) {
        optimisticQueueRequest({
          body: { raw_text: data.paper_ref, kind_hint: "paper" },
          targetPath: (id) => `/paper/${id}`,
          router,
          labels: {
            pending: "Fetching that paper…",
            queued: "Paper added to your queue.",
          },
        }).catch(() => {/* surfaced via toast */});
      }

      setCuriosityResult(data);

      // Redirect-feedback: open dialog immediately.
      if (data.action === "redirect_feedback") {
        setFeedbackOpen(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setClassifying(false);
    }
  }

  // topic_new_explored / topic_new_stub → "Add it properly" re-parses topic_hint, opens DialogModal.
  async function handleTopicNewAddIt(topicHint: string) {
    setReParsing(true);
    try {
      const parseRes = await fetch("/api/add-interest/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: topicHint, added_via: "explicit_request" }),
      });
      const parseData = (await parseRes.json()) as
        | { segments: ParsedInterestSegmentDTO[] }
        | { error: string };
      if (!parseRes.ok) throw new Error((parseData as { error?: string }).error ?? "Parse failed");

      const segments = (parseData as { segments: ParsedInterestSegmentDTO[] }).segments;
      if (!segments.length) throw new Error("Couldn't parse that topic — try different phrasing?");

      const seg = segments[0];
      const matchedSlug = seg.dedup.matched_node_slug;
      let matchedNodeId: string | null = null;
      if (matchedSlug) {
        const r = await fetch(`/api/interest/me?node_slug=${encodeURIComponent(matchedSlug)}`);
        if (r.ok) {
          const j = (await r.json()) as InterestHasResponse;
          matchedNodeId = j.node_id;
        }
      }

      const pending: SegmentPending =
        seg.dedup.verdict === "same" && matchedNodeId
          ? { case: "case1-with-match", segment: seg, matchedNodeId }
          : { case: "case1-no-match", segment: seg };

      setSegmentPending(pending);
      setDialogOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parse failed");
    } finally {
      setReParsing(false);
    }
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
          <Button type="submit" size="sm" disabled={classifying || !text.trim()}>
            {classifying ? "…" : "Go →"}
          </Button>
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </form>

      {/* Result card — rendered below the form after a successful classify */}
      {curiosityResult && (
        <CuriosityResultCard
          result={curiosityResult}
          rawText={text}
          onFeedbackOpenChange={setFeedbackOpen}
          onReParsing={reParsing}
          onTopicNewAddIt={handleTopicNewAddIt}
          onClear={reset}
          router={router}
        />
      )}

      {/* DialogModal for topic_new_explored / topic_new_stub → "Add it properly" re-parse path */}
      {segmentPending && (
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
          rawText={curiosityResult?.topic_hint ?? text}
          segment={segmentPending.segment}
          addedVia="explicit_request"
          title="Add interest"
          onComplete={() => { /* queue is refreshed on dialog close */ }}
        />
      )}

      {/* Controlled FeedbackDialog for feedback-redirect — pre-filled with the
          user's raw text. Also rendered from the result card trigger. */}
      <FeedbackDialog
        open={feedbackOpen}
        onOpenChange={setFeedbackOpen}
        initialBody={text}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------

interface ResultCardProps {
  result: CuriosityBoxResponse;
  rawText: string;
  onFeedbackOpenChange: (open: boolean) => void;
  onReParsing: boolean;
  onTopicNewAddIt: (topicHint: string) => void;
  onClear: () => void;
  router: ReturnType<typeof useRouter>;
}

function CuriosityResultCard({
  result,
  rawText,
  onFeedbackOpenChange,
  onReParsing,
  onTopicNewAddIt,
  onClear,
  router,
}: ResultCardProps) {
  const { action, message_md } = result;

  return (
    <div className="mt-4 rounded-md border border-border bg-card p-4 space-y-3">
      <p className="font-serif text-sm leading-relaxed text-muted-foreground">
        {message_md}
      </p>

      {action === "redirect_steer" && (
        <p className="text-xs text-muted-foreground">
          Use the chips above the queue to adjust the mix.
        </p>
      )}

      {action === "redirect_feedback" && (
        <Button
          size="sm"
          variant="outline"
          onClick={() => onFeedbackOpenChange(true)}
        >
          Open feedback form →
        </Button>
      )}

      {action === "answer" && result.answer_md && (
        <div className="space-y-3">
          <div className="font-serif text-sm leading-[1.7] text-foreground whitespace-pre-wrap">
            {result.answer_md}
          </div>
          {result.followon_topic_hint && (
            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  optimisticQueueRequest({
                    body: {
                      raw_text: result.followon_topic_hint!,
                      kind_hint: "problem",
                      skip_interest_add: true,
                    },
                    targetPath: queueItemPath,
                    router,
                    labels: {
                      pending: "Finding a problem on this…",
                      queued: "Problem added to your queue.",
                    },
                  }).catch(() => {/* surfaced via toast */});
                  onClear();
                }}
              >
                Give me a problem on this →
              </Button>
              <Button size="sm" variant="ghost" onClick={onClear}>
                Not now
              </Button>
            </div>
          )}
        </div>
      )}

      {action === "queued_pinned" && (
        <div className="flex flex-wrap gap-2">
          {result.queue_item_id && (
            <Button asChild size="sm">
              <Link href={`/problem/${result.queue_item_id}`}>Go to it now →</Link>
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onClear}>
            Dismiss
          </Button>
        </div>
      )}

      {action === "ingest_paper" && (
        <Button size="sm" variant="ghost" onClick={onClear}>
          Dismiss
        </Button>
      )}

      {action === "topic_new_explored" && (
        <div className="flex flex-wrap gap-2">
          {result.queue_item_id && (
            <Button asChild size="sm">
              <Link href={`/problem/${result.queue_item_id}`}>Go to it now →</Link>
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={onReParsing}
            onClick={() => onTopicNewAddIt(result.topic_hint ?? rawText)}
          >
            {onReParsing ? "…" : "Add it properly →"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onClear}>
            Dismiss
          </Button>
        </div>
      )}

      {action === "topic_new_stub" && (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            disabled={onReParsing}
            onClick={() => onTopicNewAddIt(result.topic_hint ?? rawText)}
          >
            {onReParsing ? "…" : "Add it properly →"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onClear}>
            Not now
          </Button>
        </div>
      )}

      {action === "graceful" && (
        <Button size="sm" variant="ghost" onClick={onClear}>
          OK
        </Button>
      )}

      {action === "clarify" && result.clarification_md && (
        <div className="space-y-2">
          <p className="font-serif text-sm leading-relaxed text-foreground">
            {result.clarification_md}
          </p>
          <Button size="sm" variant="ghost" onClick={onClear}>
            Let me rephrase
          </Button>
        </div>
      )}
    </div>
  );
}
