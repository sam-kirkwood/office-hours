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
//   - source="segment", specificity="ambiguous"    → path-option chips + free text
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
  const [pickedPathKeys, setPickedPathKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const isSegment = input.source === "segment";
  const segment = isSegment ? input.segment : null;
  const preNode = !isSegment ? input.preNode : null;

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

  function togglePath(key: string) {
    setPickedPathKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  // Compose the final intent text + intent_context the resolve call needs.
  function composeResolveBody(): {
    finalIntentText: string;
    intentContext: string;
    existingNodeSlug: string | null;
    relatedNodeSlug: string | null;
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
      };
    }

    // Segment path:
    const seg = segment!;
    const pickedOptions = seg.path_options.filter((p) => pickedPathKeys.has(p.key));
    let intentContext = seg.draft_intent_context || seg.mirror_back_md;
    let finalIntentText = seg.raw_text_segment || rawText;

    if (pickedOptions.length > 0) {
      const labels = pickedOptions.map((p) => p.label_md.replace(/[*_`#]/g, "").trim());
      intentContext = pickedOptions
        .map((p) => p.draft_intent_context)
        .filter((s) => s.length > 0)
        .join("; ") || intentContext;
      finalIntentText = `${seg.raw_text_segment} — ${labels.join("; ")}`;
    }

    if (trimmed.length > 0) {
      // Followup textarea content is woven into intent_context so the
      // generator sees it.
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
              Pick any that fit, or describe what you&apos;re after.
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            {segment.path_options.map((opt) => {
              const active = pickedPathKeys.has(opt.key);
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => togglePath(opt.key)}
                  className={`rounded-md border px-3 py-2 text-left text-sm transition-colors duration-[var(--duration-fast)] ${
                    active
                      ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                      : "border-border bg-card text-foreground hover:border-foreground/30"
                  }`}
                >
                  {opt.label_md.replace(/[*_`#]/g, "").trim()}
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
