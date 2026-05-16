"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { Node, NodeRating, NodeRatings } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormState {
  freeTextIntent: string;
  nodeRatings: NodeRatings;
  modeBalance: number;
}

const INITIAL_STATE: FormState = {
  freeTextIntent: "",
  nodeRatings: {},
  modeBalance: 0.5,
};

const RATING_LABELS: Record<NodeRating, string> = {
  interested: "Want to learn",
  comfortable: "Know it",
  refresh: "Want to refresh",
};

const STEPS = ["What to learn", "Rate topics", "Problems vs papers", "Ready"];

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

interface Props {
  nodes: Node[];
}

export default function SurveyForm({ nodes }: Props) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const foundationNodes = nodes.filter((n) => n.kind === "foundation");
  const interestNodes = nodes.filter((n) => n.kind === "interest");

  function setRating(slug: string, rating: NodeRating | null) {
    setForm((f) => {
      const next = { ...f.nodeRatings };
      if (rating === null) delete next[slug];
      else next[slug] = rating;
      return { ...f, nodeRatings: next };
    });
  }

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          free_text_intent: form.freeTextIntent,
          node_ratings: form.nodeRatings,
          comfort_responses: {},
          mode_balance: form.modeBalance,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Something went wrong");
      }
      router.push("/daily");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setSubmitting(false);
    }
  }

  const ratedCount = Object.keys(form.nodeRatings).length;

  return (
    <div className="mx-auto max-w-2xl px-5 py-12">
      <p className="mb-6 text-sm text-muted-foreground">
        Step {step + 1} of {STEPS.length} — {STEPS[step]}
      </p>

      {step === 0 && (
        <IntentStep
          value={form.freeTextIntent}
          onChange={(v) => setForm((f) => ({ ...f, freeTextIntent: v }))}
        />
      )}

      {step === 1 && (
        <NodeRatingStep
          foundationNodes={foundationNodes}
          interestNodes={interestNodes}
          ratings={form.nodeRatings}
          setRating={setRating}
        />
      )}

      {step === 2 && (
        <ModeBalanceStep
          value={form.modeBalance}
          onChange={(v) => setForm((f) => ({ ...f, modeBalance: v }))}
        />
      )}

      {step === 3 && (
        <ReviewStep
          freeTextIntent={form.freeTextIntent}
          ratedCount={ratedCount}
          modeBalance={form.modeBalance}
        />
      )}

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

      <div className="mt-8 flex gap-3">
        {step > 0 && (
          <Button
            type="button"
            variant="outline"
            onClick={() => setStep((s) => s - 1)}
            disabled={submitting}
          >
            Back
          </Button>
        )}
        <div className="flex-1" />
        {step < STEPS.length - 1 ? (
          <Button type="button" onClick={() => setStep((s) => s + 1)}>
            Next
          </Button>
        ) : (
          <Button type="button" onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Building your graph…" : "Start learning →"}
          </Button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 0 — Intent
// ---------------------------------------------------------------------------

function IntentStep({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">
          What do you want to learn or relearn?
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Write however feels natural — a few words or a few sentences.
        </p>
      </div>
      <Textarea
        rows={5}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. I studied physics in undergrad but it's been years. I want to get comfortable with quantum mechanics and maybe explore some modern applications."
        autoFocus
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1 — Node ratings
// ---------------------------------------------------------------------------

function NodeRatingStep({
  foundationNodes,
  interestNodes,
  ratings,
  setRating,
}: {
  foundationNodes: Node[];
  interestNodes: Node[];
  ratings: NodeRatings;
  setRating: (slug: string, rating: NodeRating | null) => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Rate the topics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          For each topic, tell us where you are. Unmarked topics are fine — we
          build from what you share.
        </p>
      </div>

      <NodeSection
        heading="Foundation topics"
        nodes={foundationNodes}
        ratings={ratings}
        setRating={setRating}
      />

      {interestNodes.length > 0 && (
        <NodeSection
          heading="Interest topics"
          headingNote="lighter — choose what excites you"
          nodes={interestNodes}
          ratings={ratings}
          setRating={setRating}
        />
      )}
    </div>
  );
}

function NodeSection({
  heading,
  headingNote,
  nodes,
  ratings,
  setRating,
}: {
  heading: string;
  headingNote?: string;
  nodes: Node[];
  ratings: NodeRatings;
  setRating: (slug: string, rating: NodeRating | null) => void;
}) {
  if (nodes.length === 0) return null;

  const sorted = [...nodes].sort((a, b) => {
    const order = { intro: 0, core: 1, advanced: 2 };
    return order[a.difficulty_hint] - order[b.difficulty_hint];
  });

  return (
    <div>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {heading}
        {headingNote && (
          <span className="ml-1 normal-case font-normal">— {headingNote}</span>
        )}
      </h2>
      <div className="flex flex-col gap-0.5">
        {sorted.map((node) => (
          <NodeRow
            key={node.slug}
            node={node}
            rating={ratings[node.slug] ?? null}
            setRating={(r) => setRating(node.slug, r)}
          />
        ))}
      </div>
    </div>
  );
}

const RATING_OPTIONS: NodeRating[] = ["interested", "comfortable", "refresh"];

function NodeRow({
  node,
  rating,
  setRating,
}: {
  node: Node;
  rating: NodeRating | null;
  setRating: (r: NodeRating | null) => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-md px-2 py-1.5 transition-colors duration-[var(--duration-fast)] hover:bg-accent/40">
      <p className="min-w-0 flex-1 text-sm text-foreground">{node.title}</p>
      <div className="flex shrink-0 gap-1">
        {RATING_OPTIONS.map((opt) => (
          <button
            key={opt}
            type="button"
            title={RATING_LABELS[opt]}
            onClick={() => setRating(rating === opt ? null : opt)}
            className={`rounded border px-2 py-0.5 text-xs transition-colors duration-[var(--duration-fast)] ${
              rating === opt
                ? opt === "comfortable"
                  ? "border-[var(--forest)] bg-[var(--forest)] text-white"
                  : opt === "refresh"
                    ? "border-amber bg-amber text-[var(--background)]"
                    : "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground"
            }`}
          >
            {opt === "interested" ? "Learn" : opt === "comfortable" ? "Know it" : "Refresh"}
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2 — Mode balance
// ---------------------------------------------------------------------------

function ModeBalanceStep({
  value,
  onChange,
}: {
  value: number;
  onChange: (v: number) => void;
}) {
  const pct = Math.round(value * 100);
  const description =
    value < 0.25
      ? "Mostly pen-and-paper problems."
      : value > 0.75
        ? "Mostly reading papers with guided questions."
        : "A mix of problems and paper engagements.";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">
          Problems or papers?
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Set the balance between pen-and-paper problems and guided paper
          readings. You can revisit this anytime.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-4">
          <span className="w-20 text-right text-sm font-medium text-foreground">
            Problems
          </span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="flex-1 accent-[var(--amber)]"
          />
          <span className="w-20 text-sm font-medium text-foreground">Papers</span>
        </div>
        <p className="text-center text-sm text-muted-foreground">{description}</p>
        <p className="text-center text-xs text-muted-foreground">{pct}% papers</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3 — Review
// ---------------------------------------------------------------------------

function ReviewStep({
  freeTextIntent,
  ratedCount,
  modeBalance,
}: {
  freeTextIntent: string;
  ratedCount: number;
  modeBalance: number;
}) {
  const pct = Math.round(modeBalance * 100);
  const modeLabel =
    modeBalance < 0.25 ? "mostly problems" : modeBalance > 0.75 ? "mostly papers" : "mixed";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Ready?</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Here&apos;s what we&apos;ll use to build your queue.
        </p>
      </div>

      <div className="flex flex-col gap-3 rounded-md border border-border bg-card p-4 text-sm">
        <Row
          label="Intent"
          value={
            freeTextIntent.trim()
              ? `"${freeTextIntent.trim().slice(0, 80)}${freeTextIntent.trim().length > 80 ? "…" : ""}"`
              : "Not provided"
          }
          dim={!freeTextIntent.trim()}
        />
        <Row
          label="Rated topics"
          value={ratedCount > 0 ? `${ratedCount} topic${ratedCount === 1 ? "" : "s"}` : "None"}
          dim={ratedCount === 0}
        />
        <Row label="Mode" value={`${modeLabel} (${pct}% papers)`} />
      </div>

      {!freeTextIntent.trim() && ratedCount === 0 && (
        <p className="text-sm text-muted-foreground">
          You haven&apos;t shared any interests yet. Your queue will start empty
          — go back to add some, or submit and add them later.
        </p>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  dim = false,
}: {
  label: string;
  value: string;
  dim?: boolean;
}) {
  return (
    <div className="flex gap-3">
      <span className="w-28 shrink-0 font-medium text-muted-foreground">{label}</span>
      <span className={dim ? "italic text-muted-foreground/60" : "text-foreground"}>{value}</span>
    </div>
  );
}
