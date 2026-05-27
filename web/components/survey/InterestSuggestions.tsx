"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export interface SurveyInterestSuggestion {
  node_id: string;
  slug: string;
  title: string;
  description_md: string;
  why_suggested_md: string;
}

interface Props {
  suggestions: SurveyInterestSuggestion[];
  initialSelectedSlugs: string[];
  initialFreeText: string;
}

export default function InterestSuggestions({
  suggestions,
  initialSelectedSlugs,
  initialFreeText,
}: Props) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set(initialSelectedSlugs));
  const [freeText, setFreeText] = useState(initialFreeText);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  async function handleNext() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey/interests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_slugs: Array.from(selected),
          free_text: freeText,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Save failed");
      }
      router.push("/survey/dialog");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSubmitting(false);
    }
  }

  const canContinue = selected.size > 0 || freeText.trim().length > 0;

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <div className="mb-6">
        <h1 className="font-serif text-2xl text-foreground">
          Based on what you&apos;ve told us, here are some things you might want to explore.
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Tap the ones that pull you in. Add anything we missed at the bottom.
        </p>
      </div>

      {suggestions.length === 0 ? (
        <p className="mb-8 rounded-md border border-dashed border-border bg-card/50 p-6 text-sm text-muted-foreground">
          No suggestions for this combination yet — that&apos;s fine. Type whatever you&apos;re curious about below.
        </p>
      ) : (
        <div className="mb-8 grid gap-3 sm:grid-cols-2">
          {suggestions.map((s) => {
            const active = selected.has(s.slug);
            return (
              <button
                key={s.slug}
                type="button"
                onClick={() => toggle(s.slug)}
                className={`flex flex-col gap-2 rounded-md border p-4 text-left transition-colors duration-[var(--duration-fast)] ${
                  active
                    ? "border-primary bg-[var(--amber-subtle)]"
                    : "border-border bg-card hover:border-foreground/30"
                }`}
              >
                <p className="font-serif text-base text-foreground">{s.title}</p>
                {s.description_md && (
                  <p className="line-clamp-2 text-sm text-muted-foreground">
                    {s.description_md.replace(/[*_`#]/g, "").trim()}
                  </p>
                )}
                {s.why_suggested_md && (
                  <p className="mt-1 text-xs italic text-[var(--forest)]/90">
                    {s.why_suggested_md}
                  </p>
                )}
              </button>
            );
          })}
        </div>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Anything else?
        </h2>
        <Textarea
          rows={3}
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder="Curious about something specific?"
        />
      </section>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <div className="flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/survey/foundations")}
          disabled={submitting}
        >
          ← Back
        </Button>
        <Button type="button" onClick={handleNext} disabled={submitting || !canContinue} size="lg">
          {submitting ? "Settling in…" : "Continue →"}
        </Button>
      </div>
    </div>
  );
}
