"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Slider as SliderPrimitive } from "radix-ui";
import { Button } from "@/components/ui/button";

interface Props {
  initialModeBalance: number;
  // TODO(2d): when the add-interest dialog can detect strong mode signals
  // (e.g. "follow LIGO papers" → papers-heavy), pass them through here so
  // we can render the "I've set this based on what you said" note.
  presetNote?: string | null;
}

export default function ModeBalanceSlider({ initialModeBalance, presetNote }: Props) {
  const router = useRouter();
  const [value, setValue] = useState(initialModeBalance);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Show the majority side's percentage so the number reads like a positive
  // statement ("60% problems") rather than an implied deficit ("40% papers").
  // The slider step is 0.05, so an explicit ±0.025 window safely catches the
  // user landing on dead-centre 0.5.
  const problemsPct = Math.round((1 - value) * 100);
  const papersPct = Math.round(value * 100);
  const majorityLabel =
    Math.abs(value - 0.5) < 0.025
      ? "Even split"
      : value < 0.5
        ? `${problemsPct}% problems`
        : `${papersPct}% papers`;
  const description =
    value < 0.25
      ? "Mostly pen-and-paper problems."
      : value > 0.75
        ? "Mostly reading papers with guided questions."
        : "A mix of problems and paper engagements.";

  async function submit(modeBalance: number) {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey/balance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode_balance: modeBalance }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Save failed");
      }
      router.push("/survey/confirm");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-5 py-10">
      <div className="mb-8">
        <h1 className="font-serif text-2xl text-foreground">Problems or papers?</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Set the rough balance between pen-and-paper problems and guided paper readings.
          You can change this anytime.
        </p>
        {presetNote && (
          <p className="mt-3 rounded-md border border-[var(--forest)]/40 bg-[var(--forest-subtle)] px-3 py-2 text-sm text-foreground">
            {presetNote}
          </p>
        )}
      </div>

      <div className="mb-8 flex flex-col gap-4 rounded-md border border-border bg-card p-6">
        <div className="flex items-center gap-4">
          <span className="w-20 text-right text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Problems
          </span>
          {/* Track + thumb only — no `SliderPrimitive.Range` so the position
              reads as a single dot, not a filled bar. The dot is what matters. */}
          <SliderPrimitive.Root
            min={0}
            max={1}
            step={0.05}
            value={[value]}
            onValueChange={(vs) => setValue(vs[0] ?? 0.5)}
            className="relative flex flex-1 touch-none items-center select-none"
          >
            <SliderPrimitive.Track className="relative h-1 grow rounded-full bg-muted" />
            <SliderPrimitive.Thumb
              aria-label="Problems versus papers"
              className="block size-4 rounded-full border-2 border-primary bg-[var(--background)] shadow-sm transition-transform duration-[var(--duration-fast)] hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            />
          </SliderPrimitive.Root>
          <span className="w-20 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Papers
          </span>
        </div>
        <p className="text-center font-serif text-sm text-foreground">{description}</p>
        <p className="text-center text-xs text-muted-foreground">{majorityLabel}</p>
      </div>

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <div className="flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/survey/interests")}
          disabled={submitting}
        >
          ← Back
        </Button>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => submit(0.5)}
            disabled={submitting}
          >
            Use the default
          </Button>
          <Button type="button" onClick={() => submit(value)} disabled={submitting} size="lg">
            {submitting ? "Saving…" : "Continue →"}
          </Button>
        </div>
      </div>
    </div>
  );
}
