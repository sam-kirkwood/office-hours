"use client";

import { Slider as SliderPrimitive } from "radix-ui";

interface Props {
  value: number;
  onChange: (value: number) => void;
}

// Shared visual core for the paper/problem balance slider. Used by the
// survey's Stage 6 ([web/components/survey/ModeBalanceSlider.tsx]) and the
// profile page ([web/components/profile/ProfileModeBalance.tsx]). The
// wrappers add the surrounding chrome (headings, buttons, save logic).

export default function ModeBalanceControl({ value, onChange }: Props) {
  // Show the majority side's percentage so the number reads like a positive
  // statement ("60% problems") rather than an implied deficit ("40% papers").
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

  return (
    <div className="flex flex-col gap-4 rounded-md border border-border bg-card p-6">
      <div className="flex items-center gap-4">
        <span className="w-20 text-right text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Problems
        </span>
        {/* Track + thumb only — no `SliderPrimitive.Range` so the position
            reads as a single dot, not a filled bar. */}
        <SliderPrimitive.Root
          min={0}
          max={1}
          step={0.05}
          value={[value]}
          onValueChange={(vs) => onChange(vs[0] ?? 0.5)}
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
  );
}
