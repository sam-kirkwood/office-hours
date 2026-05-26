"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const DOMAIN_OPTIONS = [
  { key: "physics", label: "Physics" },
  { key: "mathematics", label: "Mathematics" },
  { key: "engineering", label: "Engineering" },
  { key: "computation", label: "Computation" },
  { key: "biology", label: "Biology" },
  { key: "chemistry", label: "Chemistry" },
] as const;

const RELATIONSHIP_CARDS = [
  {
    key: "studied_reconnecting",
    label: "I studied this area",
    detail: "and want to reconnect with it",
  },
  {
    key: "encounter_at_work",
    label: "I encounter this in my work",
    detail: "and want to go deeper",
  },
  {
    key: "curious",
    label: "I'm curious",
    detail: "and want to understand it better",
  },
  {
    key: "follow_field",
    label: "I follow this field",
    detail: "and want to engage more actively",
  },
] as const;

interface Props {
  initialDomainChips: string[];
  initialRelationshipCards: string[];
  initialShortText: string;
}

export default function BackgroundForm({
  initialDomainChips,
  initialRelationshipCards,
  initialShortText,
}: Props) {
  const router = useRouter();
  const [domains, setDomains] = useState<string[]>(initialDomainChips);
  const [cards, setCards] = useState<string[]>(initialRelationshipCards);
  const [shortText, setShortText] = useState(initialShortText);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(list: string[], key: string): string[] {
    return list.includes(key) ? list.filter((k) => k !== key) : [...list, key];
  }

  async function handleNext() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey/background", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain_chips: domains,
          relationship_cards: cards,
          short_text: shortText,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Save failed");
      }
      router.push("/survey/foundations");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSubmitting(false);
    }
  }

  const canContinue = domains.length > 0 || cards.length > 0 || shortText.trim().length > 0;

  return (
    <div className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-8">
        <h1 className="font-serif text-2xl text-foreground">Tell us where you&apos;re coming from.</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          A few quick taps so the queue lands on the right things. Skip anything that doesn&apos;t fit.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Which areas interest you?
        </h2>
        <div className="flex flex-wrap gap-2">
          {DOMAIN_OPTIONS.map((opt) => {
            const active = domains.includes(opt.key);
            return (
              <button
                key={opt.key}
                type="button"
                onClick={() => setDomains((d) => toggle(d, opt.key))}
                className={`rounded-md border px-3 py-1.5 text-sm transition-colors duration-[var(--duration-fast)] ${
                  active
                    ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                }`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          What&apos;s the shape of your interest?
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">Pick whatever fits — one card or several.</p>
        <div className="grid gap-2.5 sm:grid-cols-2">
          {RELATIONSHIP_CARDS.map((card) => {
            const active = cards.includes(card.key);
            return (
              <button
                key={card.key}
                type="button"
                onClick={() => setCards((c) => toggle(c, card.key))}
                className={`rounded-md border p-4 text-left transition-colors duration-[var(--duration-fast)] ${
                  active
                    ? "border-primary bg-[var(--amber-subtle)]"
                    : "border-border bg-card hover:border-foreground/30"
                }`}
              >
                <p className="font-serif text-sm text-foreground">{card.label}</p>
                <p className="mt-1 text-sm text-muted-foreground">{card.detail}</p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Anything else?
        </h2>
        <Textarea
          rows={3}
          value={shortText}
          onChange={(e) => setShortText(e.target.value)}
          placeholder="Anything specific about your background we should know?"
        />
        <p className="mt-2 text-xs text-muted-foreground">
          Optional — a sentence or two if it&apos;s useful, nothing if not.
        </p>
      </section>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <div className="flex justify-end">
        <Button
          type="button"
          onClick={handleNext}
          disabled={submitting || !canContinue}
          size="lg"
        >
          {submitting ? "Saving…" : "Continue →"}
        </Button>
      </div>
    </div>
  );
}
