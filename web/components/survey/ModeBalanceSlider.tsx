"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import ModeBalanceControl from "@/components/ModeBalanceControl";

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

      <div className="mb-8">
        <ModeBalanceControl value={value} onChange={setValue} />
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
