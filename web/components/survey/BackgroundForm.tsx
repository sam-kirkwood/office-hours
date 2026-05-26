"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  DOMAINS,
  DOMAIN_BY_KEY,
  RELATIONSHIP_CARDS,
  type DomainKey,
  type RelationshipKey,
} from "@/lib/surveyDomains";

interface DomainEntry {
  key: DomainKey;
  subareas: string[];
  relationship: RelationshipKey | null;
}

interface Props {
  initialDomains: DomainEntry[];
  initialShortText: string;
}

export default function BackgroundForm({
  initialDomains,
  initialShortText,
}: Props) {
  const router = useRouter();
  const [entries, setEntries] = useState<DomainEntry[]>(initialDomains);
  const [shortText, setShortText] = useState(initialShortText);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedKeys = new Set(entries.map((e) => e.key));

  function toggleDomain(key: DomainKey) {
    setEntries((prev) =>
      prev.some((e) => e.key === key)
        ? prev.filter((e) => e.key !== key)
        : [...prev, { key, subareas: [], relationship: null }],
    );
  }

  function toggleSubarea(domainKey: DomainKey, subKey: string) {
    setEntries((prev) =>
      prev.map((e) =>
        e.key !== domainKey
          ? e
          : {
              ...e,
              subareas: e.subareas.includes(subKey)
                ? e.subareas.filter((s) => s !== subKey)
                : [...e.subareas, subKey],
            },
      ),
    );
  }

  function setRelationship(domainKey: DomainKey, rel: RelationshipKey) {
    setEntries((prev) =>
      prev.map((e) =>
        e.key !== domainKey
          ? e
          : { ...e, relationship: e.relationship === rel ? null : rel },
      ),
    );
  }

  async function handleNext() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey/background", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domains: entries,
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

  const canContinue = entries.length > 0 || shortText.trim().length > 0;

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <div className="mb-8">
        <h1 className="font-serif text-2xl text-foreground">
          Tell us where you&apos;re coming from.
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Pick the areas you have any kind of background or interest in — even
          ones we don&apos;t cover directly (like chem or bio) help us calibrate. You
          can leave details blank.
        </p>
      </div>

      <section className="mb-10">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Areas
        </h2>
        <div className="flex flex-wrap gap-2">
          {DOMAINS.map((d) => {
            const active = selectedKeys.has(d.key);
            return (
              <button
                key={d.key}
                type="button"
                onClick={() => toggleDomain(d.key)}
                className={`rounded-md border px-3 py-1.5 text-sm transition-colors duration-[var(--duration-fast)] ${
                  active
                    ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                    : "border-border bg-card text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                }`}
              >
                {d.label}
              </button>
            );
          })}
        </div>
      </section>

      {entries.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            A little more on each
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            For each area, tap sub-areas that are relevant — anything you&apos;ve
            studied, encounter at work, or are curious about. We use this to
            choose what to suggest, not to test you. All fields optional.
          </p>
          <div className="flex flex-col gap-5">
            {entries.map((entry) => (
              <DomainBlock
                key={entry.key}
                entry={entry}
                onToggleSubarea={(sub) => toggleSubarea(entry.key, sub)}
                onSetRelationship={(rel) => setRelationship(entry.key, rel)}
              />
            ))}
          </div>
        </section>
      )}

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

function DomainBlock({
  entry,
  onToggleSubarea,
  onSetRelationship,
}: {
  entry: DomainEntry;
  onToggleSubarea: (sub: string) => void;
  onSetRelationship: (rel: RelationshipKey) => void;
}) {
  const def = DOMAIN_BY_KEY[entry.key];
  if (!def) return null;
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <p className="mb-3 font-serif text-base text-foreground">{def.label}</p>

      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Sub-areas
      </p>
      <div className="mb-4 flex flex-wrap gap-1.5">
        {def.subareas.map((sub) => {
          const active = entry.subareas.includes(sub.key);
          return (
            <button
              key={sub.key}
              type="button"
              onClick={() => onToggleSubarea(sub.key)}
              className={`rounded-md border px-2.5 py-1 text-xs transition-colors duration-[var(--duration-fast)] ${
                active
                  ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                  : "border-border bg-background text-muted-foreground hover:border-foreground/30 hover:text-foreground"
              }`}
            >
              {sub.label}
            </button>
          );
        })}
      </div>

      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Your relationship to {def.label.toLowerCase()}
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {RELATIONSHIP_CARDS.map((card) => {
          const active = entry.relationship === card.key;
          return (
            <button
              key={card.key}
              type="button"
              onClick={() => onSetRelationship(card.key)}
              className={`rounded-md border p-3 text-left transition-colors duration-[var(--duration-fast)] ${
                active
                  ? "border-[var(--forest)] bg-[var(--forest-subtle)]"
                  : "border-border bg-background hover:border-foreground/30"
              }`}
            >
              <p className="text-sm text-foreground">{card.label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{card.detail}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
