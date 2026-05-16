"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

const KIND_CTA: Record<string, string> = {
  problem: "Work on this",
  paper_engagement: "Read paper",
  concept_review: "Review",
  refresher: "Practice again",
  suggested_interest: "Explore",
};

function KindBadge({ kind }: { kind: string }) {
  const label = KIND_LABELS[kind] ?? kind;
  if (kind === "problem") return <Badge variant="default">{label}</Badge>;
  if (kind === "paper_engagement") return <Badge variant="secondary">{label}</Badge>;
  // refresher = revisiting known material → forest outline (reading/knowledge side)
  if (kind === "refresher")
    return <Badge variant="outline" className="border-[var(--forest)]/50 text-[var(--forest)]">{label}</Badge>;
  if (kind === "suggested_interest")
    return <Badge variant="ghost">{label}</Badge>;
  return <Badge variant="ghost">{label}</Badge>;
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
    <div className="mx-auto max-w-2xl px-5 py-12">
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-xl font-semibold text-foreground">Up next</h1>
        {hasItems && (
          <button
            type="button"
            onClick={handleReroll}
            disabled={rerolling}
            className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)] disabled:opacity-40"
          >
            {rerolling ? "Finding alternatives…" : "Show me something else"}
          </button>
        )}
      </div>

      {rerollError && (
        <p className="mb-6 text-sm text-destructive">{rerollError}</p>
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
    <div className="rounded-md border border-border bg-card px-5 py-5">
      <div className="mb-3 flex items-center gap-2.5">
        <KindBadge kind={item.kind} />
        {time && <span className="text-xs text-muted-foreground">{time}</span>}
      </div>

      <p className="font-serif text-sm leading-relaxed text-foreground">
        {item.added_reason ?? defaultDescription(item.kind)}
      </p>

      <div className="mt-5">
        {item.kind === "problem" && item.ref_id ? (
          <Button asChild size="sm">
            <Link href={`/problem/${item.queue_item_id}`}>
              {KIND_CTA[item.kind]} →
            </Link>
          </Button>
        ) : item.kind === "paper_engagement" && item.ref_id ? (
          <Button asChild size="sm" variant="secondary">
            <Link href={`/paper/${item.queue_item_id}`}>
              {KIND_CTA[item.kind]} →
            </Link>
          </Button>
        ) : item.kind === "suggested_interest" ? (
          <Button asChild size="sm" variant="secondary">
            <Link href="/skill-tree">View in skill tree →</Link>
          </Button>
        ) : (
          <span className="text-sm text-muted-foreground">
            {KIND_CTA[item.kind] ?? "Open"} — coming soon
          </span>
        )}
      </div>
    </div>
  );
}

function MoreComingCard() {
  return (
    <div className="rounded-md border border-dashed border-border px-5 py-4 text-center text-sm text-muted-foreground">
      More items are being prepared — check back soon.
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border border-dashed border-border px-6 py-12 text-center">
      <p className="mb-1.5 text-sm font-medium text-foreground">
        Your queue is being built.
      </p>
      <p className="text-sm text-muted-foreground">
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
