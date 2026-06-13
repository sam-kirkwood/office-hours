"use client";

import { useState } from "react";
import Link from "next/link";
import { MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import AddPaperForm from "@/components/AddPaperForm";
import RequestBox from "@/components/RequestBox";
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
  problem: "Try this",
  paper_engagement: "Read paper",
  concept_review: "Read",
  refresher: "Look at this again",
  suggested_interest: "Explore",
};

function KindBadge({ kind, viaRefresher }: { kind: string; viaRefresher?: boolean }) {
  // A refresher is a framing on a concrete item — show the "Refresher" badge
  // regardless of the underlying kind (forest outline = revisiting known
  // material, the reading/knowledge side of the palette).
  if (viaRefresher)
    return (
      <Badge variant="outline" className="border-[var(--forest)]/50 text-[var(--forest)]">
        Refresher
      </Badge>
    );
  const label = KIND_LABELS[kind] ?? kind;
  if (kind === "problem") return <Badge variant="default">{label}</Badge>;
  if (kind === "paper_engagement") return <Badge variant="secondary">{label}</Badge>;
  if (kind === "refresher")
    return <Badge variant="outline" className="border-[var(--forest)]/50 text-[var(--forest)]">{label}</Badge>;
  if (kind === "suggested_interest")
    return <Badge variant="ghost">{label}</Badge>;
  return <Badge variant="ghost">{label}</Badge>;
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
      <div className="mb-2 flex items-baseline justify-between">
        <h1 className="text-xl font-semibold text-foreground">Up next</h1>
        <button
          type="button"
          onClick={handleReroll}
          disabled={rerolling}
          className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)] disabled:opacity-40"
        >
          {rerolling ? "Finding alternatives…" : "Show me something else"}
        </button>
      </div>

      <p className="mb-8 font-serif text-sm leading-relaxed text-muted-foreground">
        A small, curated set chosen for you — it refreshes itself as you work, so
        there&apos;s no backlog to clear. <span className="text-foreground">Concept</span> cards are
        short reads to get you oriented on a topic before the problems begin.
      </p>

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

      <div className="mt-8 pt-6 border-t border-border space-y-4">
        <AddPaperForm />
        <RequestBox />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cards
// ---------------------------------------------------------------------------

// Confirmation copy shown in place of the card once an overflow action resolves.
const RESOLVED_COPY: Record<string, string> = {
  added: "Added to your interests.",
  known: "Good to know — marked as comfortable.",
  bookmarked: "Saved to Come back to this.",
  dismissed: "Got it — less of this.",
};

type CardStatus = "idle" | "loading" | "added" | "known" | "bookmarked" | "dismissed";

function QueueCard({ item }: { item: SurfacedQueueItem }) {
  const [status, setStatus] = useState<CardStatus>("idle");

  async function post(url: string, body?: object) {
    setStatus("loading");
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) throw new Error();
      return true;
    } catch {
      setStatus("idle");
      return false;
    }
  }

  async function handleAddToInterests() {
    if (!item.ref_id) return;
    if (await post("/api/interest", { node_id: item.ref_id, added_via: "cross_pollination" }))
      setStatus("added");
  }

  // "I know this" — +comfort, advance. The problem skip route already writes a
  // marked_refreshed attempt and nudges the node toward comfortable; reuse it.
  async function handleKnow() {
    if (await post(`/api/problem/${item.queue_item_id}/skip`)) setStatus("known");
  }

  // "Bookmark" — save this, I'll manage the return (§A2).
  async function handleBookmark() {
    if (await post("/api/queue/bookmark", { queue_item_id: item.queue_item_id }))
      setStatus("bookmarked");
  }

  // "Not for me" — negative preference / down-weight (§A1).
  async function handleDismiss() {
    if (await post("/api/queue/dismiss", { queue_item_id: item.queue_item_id }))
      setStatus("dismissed");
  }

  // Once an action resolves, collapse the card to a calm confirmation line.
  if (status === "added" || status === "known" || status === "bookmarked" || status === "dismissed") {
    return (
      <div className="rounded-md border border-border bg-card px-5 py-4 text-sm text-muted-foreground">
        {RESOLVED_COPY[status]}
      </div>
    );
  }

  // Forest-outline styling used for refresher-framed items, matching the
  // "Refresher" badge family.
  const refresherBtn =
    "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest-subtle)]";
  const cta = item.via_refresher ? "Look at this again" : (KIND_CTA[item.kind] ?? "Open");

  // The from-the-card judgments live behind an unobtrusive "···" so the primary
  // CTA stays the hero (§A1: calm card, not a button dashboard). Gated by kind:
  // "I know this" is a comfort signal that only makes sense where there's a
  // problem to mark refreshed; Bookmark/Not-for-me apply to any item.
  const canBookmark =
    item.ref_id != null &&
    ["problem", "paper_engagement", "concept_review", "suggested_interest"].includes(item.kind);
  const canKnow = item.kind === "problem" && item.ref_id != null;
  const overflow = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="More actions"
          disabled={status === "loading"}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors duration-[var(--duration-fast)] disabled:opacity-40"
        >
          <MoreHorizontal className="size-4" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {canKnow && <DropdownMenuItem onClick={handleKnow}>I know this</DropdownMenuItem>}
        {canBookmark && (
          <DropdownMenuItem onClick={handleBookmark}>Bookmark for later</DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={handleDismiss}>Not for me</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  return (
    <div className="rounded-md border border-border bg-card px-5 py-5">
      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <KindBadge kind={item.kind} viaRefresher={item.via_refresher} />
        {/* d22: the topic(s) this item is drawn from. Any that just repeat the
            card title are dropped (e.g. concept reviews, where title == node). */}
        {(item.topics ?? [])
          .filter((t) => t !== item.title)
          .map((t) => (
            <span
              key={t}
              className="rounded-sm bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground"
            >
              {t}
            </span>
          ))}
      </div>

      {item.title && (
        <p className="mb-1 font-serif text-base font-semibold text-foreground leading-snug">
          {item.title}
        </p>
      )}

      <p className="font-serif text-sm leading-relaxed text-muted-foreground">
        {item.added_reason ?? defaultDescription(item.kind)}
      </p>

      {/* Action row: primary CTA is the hero (left); judgments tuck into "···". */}
      <div className="mt-5 flex items-center justify-between gap-2">
        <div>
          {item.kind === "problem" && item.ref_id ? (
            <Button
              asChild
              size="sm"
              variant={item.via_refresher ? "outline" : "default"}
              className={item.via_refresher ? refresherBtn : undefined}
            >
              <Link href={`/problem/${item.queue_item_id}`}>{cta} →</Link>
            </Button>
          ) : item.kind === "paper_engagement" && item.ref_id ? (
            <Button
              asChild
              size="sm"
              variant={item.via_refresher ? "outline" : "secondary"}
              className={item.via_refresher ? refresherBtn : undefined}
            >
              <Link href={`/paper/${item.queue_item_id}`}>
                {item.in_progress ? "Continue paper" : cta} →
              </Link>
            </Button>
          ) : item.kind === "concept_review" && item.ref_id ? (
            <Button
              asChild
              size="sm"
              variant="outline"
              className={item.via_refresher ? refresherBtn : undefined}
            >
              <Link href={`/concept-review/${item.queue_item_id}`}>{cta} →</Link>
            </Button>
          ) : item.kind === "suggested_interest" ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={status === "loading"}
              onClick={handleAddToInterests}
            >
              Add to interests
            </Button>
          ) : (
            <span className="text-sm text-muted-foreground">
              {KIND_CTA[item.kind] ?? "Open"} — coming soon
            </span>
          )}
        </div>
        {(canKnow || canBookmark || item.kind === "suggested_interest") && overflow}
      </div>
    </div>
  );
}

function MoreComingCard() {
  return (
    <div className="rounded-md border border-dashed border-border px-5 py-4 text-center text-sm text-muted-foreground">
      More to come — give it a moment.
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
    problem: "A problem on this topic.",
    paper_engagement: "A paper to read.",
    concept_review: "Worth a moment of reading.",
    refresher: "Run through this again — reinforcing what you know is just as valuable as learning something new.",
    suggested_interest: "Someone studying adjacent topics recently explored this.",
  };
  return defaults[kind] ?? "An item is waiting.";
}
