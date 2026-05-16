"use client";

import { useState } from "react";
import type { QueueResult, SurfacedQueueItem } from "@/lib/types";

// ---------------------------------------------------------------------------
// Kind display helpers
// ---------------------------------------------------------------------------

const KIND_LABELS: Record<string, string> = {
  problem: "Problem",
  paper_engagement: "Paper",
  concept_review: "Concept",
  refresher: "Refresher",
  suggested_interest: "Explore",
};

const KIND_COLORS: Record<string, string> = {
  problem: "bg-zinc-900 text-white",
  paper_engagement: "bg-blue-700 text-white",
  concept_review: "bg-violet-700 text-white",
  refresher: "bg-amber-600 text-white",
  suggested_interest: "bg-emerald-700 text-white",
};

const KIND_CTA: Record<string, string> = {
  problem: "Work on this →",
  paper_engagement: "Read paper →",
  concept_review: "Review →",
  refresher: "Practice again →",
  suggested_interest: "Explore →",
};

function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

function kindColor(kind: string): string {
  return KIND_COLORS[kind] ?? "bg-zinc-600 text-white";
}

function kindCta(kind: string): string {
  return KIND_CTA[kind] ?? "Open →";
}

function timeRange(low: number | null, high: number | null): string | null {
  if (!low && !high) return null;
  if (low && high && low !== high) return `${low}–${high} min`;
  return `${low ?? high} min`;
}

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

interface Props {
  initialResult: QueueResult;
}

export default function DailyView({ initialResult }: Props) {
  const [result, setResult] = useState<QueueResult>(initialResult);
  const [rerolling, setRerolling] = useState(false);
  const [rerollError, setRerollError] = useState<string | null>(null);

  async function handleReroll() {
    setRerolling(true);
    setRerollError(null);
    try {
      const res = await fetch("/api/queue/reroll", { method: "POST" });
      const data = (await res.json()) as QueueResult & { error?: string };
      if (!res.ok) throw new Error(data.error ?? "Reroll failed");
      setResult(data);
    } catch (err) {
      setRerollError(err instanceof Error ? err.message : "Reroll failed");
    } finally {
      setRerolling(false);
    }
  }

  const { items, more_coming } = result;
  const hasItems = items.length > 0;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-xl font-semibold text-zinc-900">Up next</h1>
        {hasItems && (
          <button
            type="button"
            onClick={handleReroll}
            disabled={rerolling}
            className="text-xs text-zinc-400 underline-offset-2 transition hover:text-zinc-700 hover:underline disabled:opacity-40"
          >
            {rerolling ? "Finding alternatives…" : "Show me something else"}
          </button>
        )}
      </div>

      {rerollError && (
        <p className="mb-4 text-sm text-red-600">{rerollError}</p>
      )}

      {!hasItems ? (
        <EmptyState />
      ) : (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <QueueCard key={item.queue_item_id} item={item} />
          ))}
          {more_coming && <MoreComingCard />}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

function QueueCard({ item }: { item: SurfacedQueueItem }) {
  const time = timeRange(item.time_estimate_minutes_low, item.time_estimate_minutes_high);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-5 py-4">
      <div className="mb-3 flex items-center gap-2">
        <span
          className={`rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${kindColor(item.kind)}`}
        >
          {kindLabel(item.kind)}
        </span>
        {time && <span className="text-xs text-zinc-400">{time}</span>}
      </div>

      <p className="mb-1 text-sm text-zinc-800">
        {item.added_reason ?? defaultDescription(item.kind)}
      </p>

      <div className="mt-4">
        <span className="text-sm font-medium text-zinc-400 cursor-default">
          {kindCta(item.kind)}
        </span>
      </div>
    </div>
  );
}

function MoreComingCard() {
  return (
    <div className="rounded-xl border border-dashed border-zinc-200 px-5 py-4 text-center text-sm text-zinc-400">
      More items are being prepared — check back soon.
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-zinc-200 px-6 py-10 text-center">
      <p className="mb-1 text-sm font-medium text-zinc-700">
        Your queue is being built.
      </p>
      <p className="text-sm text-zinc-400">
        Add interests from your profile or check back after your next session.
      </p>
    </div>
  );
}

function defaultDescription(kind: string): string {
  const defaults: Record<string, string> = {
    problem: "A problem is ready for you.",
    paper_engagement: "A paper is queued for reading.",
    concept_review: "A concept is ready for review.",
    refresher: "Time to revisit something you've worked on.",
    suggested_interest: "A new topic has been suggested based on your interests.",
  };
  return defaults[kind] ?? "An item is waiting.";
}
