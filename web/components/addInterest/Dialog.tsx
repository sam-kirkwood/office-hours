"use client";

// Add-interest dialog — survey-and-difficulty-design.md §2.
//
// One Dialog instance handles ONE segment (or one pre-known node). The
// orchestrator (Stage 4 page, RequestBox modal, NodePanel modal) calls
// /add-interest/parse first, then renders one Dialog per parsed segment.
//
// State machine:
//   gathering → resolving → resolved → onResolved fires
//
// "gathering" presents different UI based on input:
//   - source="segment", specificity="specific"     → optional followup textarea
//   - source="segment", specificity="ambiguous"    → rich path cards (single-select) + free text
//   - source="preNode"                             → followup textarea (no parse)
//
// On resolve we hand the caller everything it needs to run the concept tour.

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type {
  DialogInput,
  DialogPresentation,
  DialogResolved,
  AddedVia,
} from "./types";
import type { RichPath, Altitude } from "@/lib/pythonApi";

// Map the parser's implicit_intent to a default altitude (Phase 13 Step 3).
// teach→new, refresh→coming_back, consolidate→go_deep. The user can override
// the pre-set with the chips below.
const INTENT_TO_ALTITUDE: Record<string, Altitude> = {
  teach: "new",
  refresh: "coming_back",
  consolidate: "go_deep",
};

const ALTITUDE_OPTIONS: Array<{ value: Altitude; label: string; blurb: string }> = [
  { value: "new", label: "New to me", blurb: "Start from the ground up." },
  { value: "coming_back", label: "Coming back", blurb: "I've seen this before — jog my memory." },
  { value: "go_deep", label: "I know this — go deep", blurb: "Skip the intro; assume the apparatus." },
];

interface Props {
  rawText: string;
  input: DialogInput;
  addedVia: AddedVia;
  presentation?: DialogPresentation;
  onResolved: (result: DialogResolved) => void;
  onCancel?: () => void;
}

type Phase = "gathering" | "resolving" | "error";

export default function Dialog({
  rawText,
  input,
  addedVia,
  presentation = "full-page",
  onResolved,
  onCancel,
}: Props) {
  const [phase, setPhase] = useState<Phase>("gathering");
  const [followupText, setFollowupText] = useState<string>(
    input.source === "preNode" ? input.preNode.defaultIntentContext ?? "" : "",
  );
  const [pickedPathKey, setPickedPathKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isSegment = input.source === "segment";
  const segment = isSegment ? input.segment : null;
  const preNode = !isSegment ? input.preNode : null;

  // Altitude (Phase 13 Step 3) — pre-set from the parser's implicit_intent
  // when we have a segment; default "new" otherwise. User can override.
  const [altitude, setAltitude] = useState<Altitude>(
    (segment && INTENT_TO_ALTITUDE[segment.implicit_intent]) || "new",
  );

  const mirrorBack =
    segment?.mirror_back_md ??
    preNode?.mirrorOverride ??
    `Got it — ${preNode?.title ?? "this one"}.`;

  const followupPrompt =
    preNode?.followupPromptOverride ??
    segment?.optional_followup_md ??
    "Want to tell me more about what draws you to this?";

  const showPaths = isSegment && segment!.specificity === "ambiguous";
  const showFollowup = !showPaths; // specific OR preNode → followup textarea

  function selectPath(key: string) {
    setPickedPathKey((prev) => (prev === key ? null : key));
  }

  // Compose the final intent text + intent_context + pathJson the resolve call needs.
  function composeResolveBody(): {
    finalIntentText: string;
    intentContext: string;
    existingNodeSlug: string | null;
    relatedNodeSlug: string | null;
    pathJson: RichPath | null;
  } {
    const trimmed = followupText.trim();

    if (preNode) {
      // Pre-known node: link to it via existing_node_slug. intent_context is
      // whatever the user typed (or the existing default if they made no edit).
      const intentContext =
        trimmed.length > 0
          ? trimmed
          : preNode.defaultIntentContext ?? `interest in ${preNode.title}`;
      return {
        finalIntentText: preNode.title,
        intentContext,
        existingNodeSlug: preNode.slug,
        relatedNodeSlug: null,
        pathJson: null,
      };
    }

    // Segment path:
    const seg = segment!;
    const pickedOption = pickedPathKey
      ? seg.path_options.find((p) => p.key === pickedPathKey) ?? null
      : null;
    let intentContext = seg.draft_intent_context || seg.mirror_back_md;
    let finalIntentText = seg.raw_text_segment || rawText;

    // Build pathJson (structured facts) separately from the prose intentContext.
    let pathJson: RichPath | null = null;
    if (pickedOption) {
      const label = pickedOption.label_md.replace(/[*_`#]/g, "").trim();
      intentContext = pickedOption.draft_intent_context || intentContext;
      finalIntentText = `${seg.raw_text_segment} — ${label}`;
      // Exclude draft_intent_context — it's prose, not a structured fact.
      const { draft_intent_context: _omit, ...richFields } = pickedOption;
      pathJson = richFields;
    }

    if (trimmed.length > 0) {
      // Freetext is woven into intent_context prose only — not into path_json.
      intentContext = intentContext
        ? `${intentContext}. User added: ${trimmed}`
        : trimmed;
    }

    return {
      finalIntentText,
      intentContext,
      existingNodeSlug:
        seg.dedup.verdict === "same" ? seg.dedup.matched_node_slug : null,
      relatedNodeSlug:
        seg.dedup.verdict === "related" ? seg.dedup.matched_node_slug : null,
      pathJson,
    };
  }

  async function handleResolve() {
    setError(null);
    setPhase("resolving");
    try {
      const body = composeResolveBody();
      const res = await fetch("/api/add-interest/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          added_via: addedVia,
          raw_text: rawText,
          final_intent_text: body.finalIntentText,
          intent_context: body.intentContext,
          existing_node_slug: body.existingNodeSlug,
          related_node_slug: body.relatedNodeSlug,
          path_json: body.pathJson,
          altitude,
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error((j as { error?: string }).error ?? "Resolve failed");
      }
      const data = (await res.json()) as DialogResolved;
      onResolved(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed");
      setPhase("error");
    }
  }

  const containerCls =
    presentation === "modal"
      ? "flex flex-col gap-5"
      : "mx-auto max-w-2xl px-5 py-10 flex flex-col gap-6";

  const ctaLabel = phase === "resolving" ? "Settling in…" : "Add this interest";

  return (
    <div className={containerCls}>
      <p className="font-serif text-lg leading-[1.7] text-foreground">{mirrorBack}</p>

      {showPaths && segment && (
        <div className="flex flex-col gap-3">
          <p className="text-sm leading-relaxed text-muted-foreground">
            That covers a few different angles — which sounds closest?
            <span className="block text-xs italic text-muted-foreground/80 mt-1">
              Pick one, or describe what you&apos;re after below.
            </span>
          </p>
          <div className="flex flex-col gap-2">
            {segment.path_options.map((opt) => {
              const active = pickedPathKey === opt.key;
              const mathLabel: Record<string, string> = {
                algebra: "Algebra",
                calculus: "Calculus",
                linear_algebra: "Linear algebra",
                heavy_math: "Heavy mathematics",
                qualitative: "Qualitative",
              };
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => selectPath(opt.key)}
                  className={`rounded-md border px-3 py-2.5 text-left transition-colors duration-[var(--duration-fast)] ${
                    active
                      ? "border-primary bg-[var(--amber-subtle)]"
                      : "border-border bg-card hover:border-foreground/30"
                  }`}
                >
                  <span className="block text-sm font-medium text-foreground">
                    {opt.label_md.replace(/[*_`#]/g, "").trim()}
                  </span>
                  {opt.what_you_learn && (
                    <span className="mt-0.5 block text-sm leading-relaxed text-muted-foreground">
                      {opt.what_you_learn}
                    </span>
                  )}
                  {opt.endpoint && (
                    <span className="mt-1 block text-xs italic text-muted-foreground/80">
                      → {opt.endpoint}
                    </span>
                  )}
                  {opt.math_intensity && (
                    <span className="mt-1.5 inline-block rounded border border-border px-1.5 py-0.5 text-xs text-muted-foreground">
                      {mathLabel[opt.math_intensity] ?? opt.math_intensity}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
          <Textarea
            rows={2}
            value={followupText}
            onChange={(e) => setFollowupText(e.target.value)}
            placeholder="Or tell me what you're after."
          />
        </div>
      )}

      {showFollowup && (
        <div className="flex flex-col gap-2">
          <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            {followupPrompt.replace(/[*_`#]/g, "").trim()}
          </label>
          <Textarea
            rows={3}
            value={followupText}
            onChange={(e) => setFollowupText(e.target.value)}
            placeholder="A sentence or two is plenty — or skip and we'll start from what you said."
          />
        </div>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Where are you with this?
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {ALTITUDE_OPTIONS.map((opt) => {
            const active = altitude === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => setAltitude(opt.value)}
                aria-pressed={active}
                className={`flex-1 rounded-md border px-3 py-2 text-left transition-colors duration-[var(--duration-fast)] ${
                  active
                    ? "border-primary bg-[var(--amber-subtle)]"
                    : "border-border bg-card hover:border-foreground/30"
                }`}
              >
                <span className="block text-sm font-medium text-foreground">
                  {opt.label}
                </span>
                <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                  {opt.blurb}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        {onCancel ? (
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            disabled={phase === "resolving"}
          >
            Cancel
          </Button>
        ) : (
          <span />
        )}
        <Button
          type="button"
          onClick={handleResolve}
          disabled={phase === "resolving"}
          size="lg"
        >
          {ctaLabel} →
        </Button>
      </div>
    </div>
  );
}
