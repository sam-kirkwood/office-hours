"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// Admin-only affordance for iterative testing of the seven-stage survey.
// Hits POST /api/survey/reset, then bounces the user to /survey so they
// start at Stage 1.

export default function RestartSurveyButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (busy) return;
    if (!confirm("Wipe your survey, interests, node states, and queue items?")) {
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/survey/reset", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Reset failed");
      }
      // Hard reload so the survey layout re-evaluates its gate.
      window.location.href = "/survey";
    } catch (err) {
      alert(err instanceof Error ? err.message : "Reset failed");
      setBusy(false);
      router.refresh();
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className="rounded-md border border-dashed border-border bg-card px-2 py-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground transition-colors duration-[var(--duration-fast)] hover:border-foreground/30 hover:text-foreground disabled:opacity-50"
      title="Admin: wipe survey state and re-run from Stage 1"
    >
      {busy ? "Resetting…" : "Restart (admin)"}
    </button>
  );
}
