"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import MarkdownLatex from "@/lib/markdown";
import type { Paper, PaperEngagement, PaperAnswer, PaperQuestion } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ReadingBlock({ source, className = "" }: { source: string; className?: string }) {
  return (
    <div
      className={`font-serif text-base leading-[1.7] text-foreground
        [&_p]:mb-4 [&_p:last-child]:mb-0
        [&_strong]:font-semibold [&_em]:italic
        [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-1.5
        [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-1.5
        [&_code]:font-mono [&_code]:text-sm [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
        ${className}`}
    >
      <MarkdownLatex source={source} />
    </div>
  );
}

function KindLabel({ kind }: { kind: string }) {
  const labels: Record<string, string> = {
    comprehension: "Comprehension",
    critical: "Critical thinking",
    connective: "Connection",
  };
  return (
    <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
      {labels[kind] ?? kind}
    </span>
  );
}

function paperUrl(paper: Paper): string | null {
  if (paper.external_url) return paper.external_url;
  if (paper.arxiv_id) return `https://arxiv.org/abs/${paper.arxiv_id}`;
  if (paper.doi) return `https://doi.org/${paper.doi}`;
  return null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  queueItemId: string;
  paper: Paper;
  engagement: PaperEngagement;
  existingAnswers: PaperAnswer[];
}

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

export default function PaperView({ queueItemId, paper, engagement, existingAnswers }: Props) {
  const router = useRouter();

  const sortedQuestions: PaperQuestion[] = [...(engagement.questions_json ?? [])].sort(
    (a, b) => a.order - b.order,
  );

  const answerByQuestionId: Record<string, PaperAnswer> = Object.fromEntries(
    existingAnswers.map((a) => [a.question_id, a]),
  );

  const isCompleted = engagement.state === "completed";

  // Start at the engagement's saved index, or 0
  const initialQuestionIdx = Math.min(
    engagement.current_question_index,
    sortedQuestions.length - 1,
  );

  const [phase, setPhase] = useState<"intro" | "questions" | "qa">(
    isCompleted ? "qa" : engagement.current_question_index > 0 ? "questions" : "intro",
  );
  const [currentIdx, setCurrentIdx] = useState(initialQuestionIdx < 0 ? 0 : initialQuestionIdx);
  const [answers, setAnswers] = useState<Record<string, PaperAnswer>>(answerByQuestionId);
  const [draftAnswer, setDraftAnswer] = useState("");
  const [submittingAnswer, setSubmittingAnswer] = useState(false);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [skipping, setSkipping] = useState(false);

  // Q&A state
  const [qaTurns, setQaTurns] = useState<{ user: string; claude: string }[]>([]);
  const [qaInput, setQaInput] = useState("");
  const [qaSubmitting, setQaSubmitting] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);

  const currentQuestion = sortedQuestions[currentIdx] ?? null;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function handleSkip() {
    setSkipping(true);
    try {
      await fetch(`/api/paper/${queueItemId}/skip`, { method: "POST" });
      router.push("/daily");
    } catch {
      setSkipping(false);
    }
  }

  async function handleSubmitAnswer() {
    if (!currentQuestion || !draftAnswer.trim()) return;
    setSubmittingAnswer(true);
    setAnswerError(null);
    try {
      const res = await fetch(`/api/paper/${queueItemId}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          engagement_id: engagement.id,
          question_id: currentQuestion.id,
          user_response_md: draftAnswer.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to submit answer");

      setAnswers((prev) => ({
        ...prev,
        [currentQuestion.id]: {
          id: "",
          engagement_id: engagement.id,
          question_id: currentQuestion.id,
          user_response_md: draftAnswer.trim(),
          claude_response_md: data.claude_response_md,
          submitted_at: new Date().toISOString(),
        },
      }));
      setDraftAnswer("");

      if (data.next_question_index === -1) {
        setPhase("qa");
      }
    } catch (err) {
      setAnswerError(err instanceof Error ? err.message : "Error");
    } finally {
      setSubmittingAnswer(false);
    }
  }

  function handleNextQuestion() {
    if (currentIdx < sortedQuestions.length - 1) {
      setCurrentIdx((i) => i + 1);
      setDraftAnswer("");
    } else {
      setPhase("qa");
    }
  }

  async function handleAsk() {
    if (!qaInput.trim()) return;
    const msg = qaInput.trim();
    setQaSubmitting(true);
    setQaError(null);
    setQaInput("");
    try {
      const res = await fetch(`/api/paper/${queueItemId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ engagement_id: engagement.id, user_message_md: msg }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to ask");
      setQaTurns((prev) => [...prev, { user: msg, claude: data.claude_response_md }]);
    } catch (err) {
      setQaError(err instanceof Error ? err.message : "Error");
    } finally {
      setQaSubmitting(false);
    }
  }

  async function handleDone() {
    setMarking(true);
    try {
      // Mark queue item as done by calling skip (which sets dismissed) —
      // instead use a dedicated done endpoint: we'll update queue_items directly
      // via the answer route's side effect. For now POST to skip and navigate.
      // Actually we need to mark as 'done', not 'dismissed'. Use the admin client
      // via a thin route — for Phase 6-rev, we reuse skip but mark state=done.
      const res = await fetch(`/api/paper/${queueItemId}/done`, { method: "POST" });
      if (!res.ok) {
        // done route may not exist yet — fall back to navigating anyway
      }
    } catch {
      // best-effort
    }
    router.push("/daily");
  }

  const url = paperUrl(paper);
  const authorsStr =
    Array.isArray(paper.authors_json) && paper.authors_json.length > 0
      ? paper.authors_json.slice(0, 3).join(", ") + (paper.authors_json.length > 3 ? " et al." : "")
      : null;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="mx-auto max-w-2xl px-5 py-12">

      {/* Back link */}
      <Link
        href="/daily"
        className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
      >
        ← Today
      </Link>

      {/* Paper meta */}
      <div className="mt-8 mb-10">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">Paper</Badge>
          {paper.year && (
            <span className="text-xs text-muted-foreground">{paper.year}</span>
          )}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground leading-snug">
          {paper.title}
        </h1>
        {authorsStr && (
          <p className="mt-1 text-sm text-muted-foreground">{authorsStr}</p>
        )}
      </div>

      {/* Section A — Why this paper (always visible) */}
      <section className="mb-10">
        {engagement.why_this_md && (
          <div className="mb-6 border-l-2 border-[var(--forest)] pl-5">
            <ReadingBlock source={engagement.why_this_md} className="text-sm" />
          </div>
        )}

        {engagement.orienting_concepts_json?.length > 0 && (
          <div className="mb-6">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Orienting concepts
            </p>
            <div className="flex flex-wrap gap-2">
              {engagement.orienting_concepts_json.map((concept) => (
                <Badge key={concept} variant="outline" className="font-serif text-xs">
                  {concept}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          {url && (
            <Button asChild size="sm" variant="secondary">
              <a href={url} target="_blank" rel="noopener noreferrer">
                Open paper ↗
              </a>
            </Button>
          )}
          {phase === "intro" && (
            <>
              <Button size="sm" onClick={() => setPhase("questions")}>
                Start reading →
              </Button>
              <button
                type="button"
                onClick={handleSkip}
                disabled={skipping}
                className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)] disabled:opacity-40"
              >
                {skipping ? "Skipping…" : "Skip — not for me"}
              </button>
            </>
          )}
        </div>
      </section>

      {/* Section B — Guided questions */}
      {(phase === "questions" || phase === "qa") && sortedQuestions.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-6 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Guided questions
          </h2>

          {sortedQuestions.map((q, idx) => {
            const answered = answers[q.id];
            const isCurrent = idx === currentIdx && phase === "questions";
            const isPast = answered != null;

            if (!isPast && !isCurrent) return null;

            return (
              <div key={q.id} className="mb-8">
                <div className="mb-2 flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Q{idx + 1}</span>
                  <KindLabel kind={q.kind} />
                </div>

                <div className="mb-4 rounded-md border border-border bg-card px-5 py-4">
                  <ReadingBlock source={q.prompt_md} />
                </div>

                {isPast && answered.user_response_md && (
                  <div className="mb-3 pl-4 border-l-2 border-muted">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Your answer
                    </p>
                    <ReadingBlock source={answered.user_response_md} className="text-sm" />
                  </div>
                )}

                {isPast && answered.claude_response_md && (
                  <div className="pl-4 border-l-2 border-[var(--forest)]">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Feedback
                    </p>
                    <ReadingBlock source={answered.claude_response_md} className="text-sm" />
                  </div>
                )}

                {isCurrent && !answered && (
                  <div className="mt-4 space-y-3">
                    <Textarea
                      value={draftAnswer}
                      onChange={(e) => setDraftAnswer(e.target.value)}
                      placeholder="Write your answer… Markdown and LaTeX ($...$) are supported."
                      rows={5}
                      className="font-serif text-sm"
                    />
                    {answerError && (
                      <p className="text-sm text-destructive">{answerError}</p>
                    )}
                    <Button
                      size="sm"
                      onClick={handleSubmitAnswer}
                      disabled={submittingAnswer || !draftAnswer.trim()}
                    >
                      {submittingAnswer ? "Submitting…" : "Submit answer"}
                    </Button>
                  </div>
                )}

                {isCurrent && answered && (
                  <div className="mt-4">
                    {idx < sortedQuestions.length - 1 ? (
                      <Button size="sm" onClick={handleNextQuestion}>
                        Next question →
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => setPhase("qa")}>
                        Continue to free Q&A →
                      </Button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </section>
      )}

      {/* Section C — Free Q&A */}
      {phase === "qa" && (
        <section className="mb-10">
          <h2 className="mb-6 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Ask about the paper
          </h2>

          {qaTurns.length === 0 && (
            <p className="mb-4 text-sm text-muted-foreground font-serif">
              Ask anything about the paper — Claude will answer based on the abstract and domain knowledge.
            </p>
          )}

          <div className="space-y-6 mb-6">
            {qaTurns.map((turn, i) => (
              <div key={i}>
                <div className="mb-2 pl-4 border-l-2 border-muted">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">You</p>
                  <ReadingBlock source={turn.user} className="text-sm" />
                </div>
                <div className="pl-4 border-l-2 border-[var(--forest)]">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Claude</p>
                  <ReadingBlock source={turn.claude} className="text-sm" />
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            <Textarea
              value={qaInput}
              onChange={(e) => setQaInput(e.target.value)}
              placeholder="Ask a question about this paper…"
              rows={3}
              className="font-serif text-sm"
            />
            {qaError && <p className="text-sm text-destructive">{qaError}</p>}
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                variant="secondary"
                onClick={handleAsk}
                disabled={qaSubmitting || !qaInput.trim()}
              >
                {qaSubmitting ? "Asking…" : "Ask"}
              </Button>
              <Button size="sm" onClick={handleDone} disabled={marking}>
                {marking ? "Saving…" : "Done →"}
              </Button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
