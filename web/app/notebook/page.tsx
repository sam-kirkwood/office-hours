"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDown } from "lucide-react";
import MarkdownLatex from "@/lib/markdown";
import type { NotebookEntry } from "@/lib/types";

function KindBadge({ kind }: { kind: string }) {
  if (kind === "problem_attempt")
    return <Badge variant="default">Problem</Badge>;
  if (kind === "concept_review")
    return (
      <Badge variant="outline" className="border-[var(--forest)]/50 text-[var(--forest)]">
        Concept
      </Badge>
    );
  return <Badge variant="secondary">Paper</Badge>;
}

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

interface Interest {
  node_id: string;
  slug: string;
  title: string;
}

interface ComeBackBookmark {
  node_id: string;
  slug: string;
  title: string;
  created_at: string;
}

interface ComeBackDeferred {
  queue_item_id: string;
  kind: string;
  ref_id: string | null;
  title: string;
  node_slug: string | null;
  topics: string[];
  statement_md: string | null;
  context_md: string | null;
  deferred_at: string | null;
}

const ALL_TAB = "__all__";
const COME_BACK_TAB = "__come_back__";

export default function NotebookPage() {
  const [entries, setEntries] = useState<NotebookEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [interests, setInterests] = useState<Interest[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(ALL_TAB);

  // Come back to this (g1)
  const [comeBack, setComeBack] = useState<{
    bookmarks: ComeBackBookmark[];
    deferred: ComeBackDeferred[];
  }>({ bookmarks: [], deferred: [] });
  const [comeBackLoading, setComeBackLoading] = useState(true);
  const [resuming, setResuming] = useState<string | null>(null);

  const fetchEntries = useCallback(async (search: string) => {
    setLoading(true);
    setError(null);
    try {
      // Load a wider window so the by-interest tabs can filter client-side.
      const params = new URLSearchParams({ limit: "50" });
      if (search.trim()) params.set("q", search.trim());
      const res = await fetch(`/api/notebook?${params}`);
      if (!res.ok) throw new Error("Failed to load notebook");
      const data = await res.json();
      setEntries(data.entries);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchComeBack = useCallback(async () => {
    setComeBackLoading(true);
    try {
      const res = await fetch("/api/notebook/come-back");
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setComeBack({ bookmarks: data.bookmarks ?? [], deferred: data.deferred ?? [] });
    } catch {
      setComeBack({ bookmarks: [], deferred: [] });
    } finally {
      setComeBackLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries("");
    fetchComeBack();
    fetch("/api/interest/list")
      .then((r) => r.json())
      .then((d) => setInterests(d.interests ?? []))
      .catch(() => setInterests([]));
  }, [fetchEntries, fetchComeBack]);

  useEffect(() => {
    const t = setTimeout(() => fetchEntries(q), 300);
    return () => clearTimeout(t);
  }, [q, fetchEntries]);

  async function handleResume(queueItemId: string) {
    setResuming(queueItemId);
    try {
      const res = await fetch("/api/queue/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queue_item_id: queueItemId }),
      });
      if (!res.ok) throw new Error("Failed");
      // Optimistically drop it from the deferred list.
      setComeBack((prev) => ({
        ...prev,
        deferred: prev.deferred.filter((d) => d.queue_item_id !== queueItemId),
      }));
    } catch {
      /* leave it in place; the user can retry */
    } finally {
      setResuming(null);
    }
  }

  // Entries shown for the active entry-tab (All or a specific interest slug).
  const visibleEntries = useMemo(() => {
    if (activeTab === ALL_TAB || activeTab === COME_BACK_TAB) return entries;
    return entries.filter((e) => e.topic_node_slugs.includes(activeTab));
  }, [entries, activeTab]);

  const comeBackCount = comeBack.bookmarks.length + comeBack.deferred.length;
  const interestActive = activeTab !== ALL_TAB && activeTab !== COME_BACK_TAB;
  const activeInterestTitle = interestActive
    ? (interests.find((i) => i.slug === activeTab)?.title ?? "Topics")
    : "Topics";

  return (
    <div className="mx-auto max-w-3xl px-5 py-12">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-xl font-semibold text-foreground">Notebook</h1>
        {!loading && (
          <span className="text-sm text-muted-foreground">
            {total} {total === 1 ? "entry" : "entries"}
          </span>
        )}
      </div>

      {/* Tab strip (n1): All · Topics dropdown (by interest) · Come back to this */}
      <div className="mb-6 flex items-center gap-1 border-b border-border">
        <TabButton
          label="All"
          active={activeTab === ALL_TAB}
          onClick={() => setActiveTab(ALL_TAB)}
        />
        {interests.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className={`${tabClass(interestActive)} flex max-w-[14rem] items-center gap-1`}
              >
                <span className="truncate">
                  {interestActive ? activeInterestTitle : "Topics"}
                </span>
                <ChevronDown className="size-3.5 shrink-0" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="max-h-72 w-56 overflow-y-auto">
              {interests.map((i) => (
                <DropdownMenuItem key={i.node_id} onClick={() => setActiveTab(i.slug)}>
                  {i.title}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        <TabButton
          label="Come back to this"
          count={comeBackLoading ? undefined : comeBackCount}
          active={activeTab === COME_BACK_TAB}
          onClick={() => setActiveTab(COME_BACK_TAB)}
        />
      </div>

      {activeTab === COME_BACK_TAB ? (
        <ComeBackPanel
          loading={comeBackLoading}
          bookmarks={comeBack.bookmarks}
          deferred={comeBack.deferred}
          resuming={resuming}
          onResume={handleResume}
        />
      ) : (
        <>
          <Input
            type="search"
            placeholder="Search entries…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="mb-8"
          />

          {error && <p className="mb-6 text-sm text-destructive">{error}</p>}

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-md border border-border bg-card px-5 py-4 space-y-2">
                  <div className="flex items-center gap-2">
                    <Skeleton className="h-4 w-14" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ))}
            </div>
          ) : visibleEntries.length === 0 ? (
            <div className="rounded-md border border-dashed border-border px-6 py-12 text-center">
              <p className="text-sm text-muted-foreground">
                {q
                  ? "No entries match your search."
                  : activeTab === ALL_TAB
                    ? "No notebook entries yet. Complete a problem to create your first one."
                    : "Nothing here yet for this interest."}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {visibleEntries.map((entry) => (
                <Link
                  key={entry.id}
                  href={`/notebook/${entry.id}`}
                  className="block rounded-md border border-border bg-card px-5 py-4 transition-colors duration-[var(--duration-fast)] hover:bg-accent/40"
                >
                  <div className="mb-2 flex items-center gap-2.5">
                    <KindBadge kind={entry.entry_kind} />
                    <span className="text-xs text-muted-foreground">{fmt(entry.created_at)}</span>
                  </div>
                  <p className="font-medium text-foreground">{entry.title}</p>
                  {entry.topic_node_slugs.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {entry.topic_node_slugs.map((slug) => (
                        <Badge key={slug} variant="ghost" className="text-[10px]">
                          {slug.replace(/-/g, "‑")}
                        </Badge>
                      ))}
                    </div>
                  )}
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Shared underline-tab styling, reused by the All / Come back to this tabs and
// the Topics dropdown trigger so they read as one strip.
function tabClass(active: boolean) {
  return `-mb-px shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors duration-[var(--duration-fast)] ${
    active
      ? "border-primary font-medium text-foreground"
      : "border-transparent text-muted-foreground hover:text-foreground"
  }`;
}

function TabButton({
  label,
  active,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className={tabClass(active)}>
      {label}
      {typeof count === "number" && count > 0 && (
        <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {count}
        </span>
      )}
    </button>
  );
}

function ComeBackPanel({
  loading,
  bookmarks,
  deferred,
  resuming,
  onResume,
}: {
  loading: boolean;
  bookmarks: ComeBackBookmark[];
  deferred: ComeBackDeferred[];
  resuming: string | null;
  onResume: (id: string) => void;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <Skeleton key={i} className="h-16 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (bookmarks.length === 0 && deferred.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border px-6 py-12 text-center">
        <p className="text-sm text-muted-foreground">
          Nothing parked yet. Bookmark a topic in the skill tree, or tap
          “not ready yet” on a problem, and it&apos;ll wait for you here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {deferred.length > 0 && (
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Set aside for later
          </h2>
          <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
            Problems you weren&apos;t ready for. We&apos;ll bring them back when the
            groundwork lands — or pull one in now.
          </p>
          <ul className="space-y-3">
            {deferred.map((d) => (
              <DeferredItem
                key={d.queue_item_id}
                item={d}
                resuming={resuming === d.queue_item_id}
                onResume={() => onResume(d.queue_item_id)}
              />
            ))}
          </ul>
        </section>
      )}

      {bookmarks.length > 0 && (
        <section>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Bookmarked topics
          </h2>
          <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
            Topics you saved to explore. Open one in the skill tree to pull up a
            problem or add it to your interests.
          </p>
          <ul className="space-y-3">
            {bookmarks.map((b) => (
              <li
                key={b.node_id}
                className="flex items-center justify-between gap-3 rounded-md border border-border bg-card px-5 py-4"
              >
                <p className="min-w-0 truncate font-serif text-base text-foreground">
                  {b.title}
                </p>
                <Link
                  href={`/skill-tree?node=${encodeURIComponent(b.slug)}`}
                  className="shrink-0 text-sm text-[var(--forest)] underline-offset-2 hover:underline"
                >
                  See in skill tree →
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function DeferredItem({
  item,
  resuming,
  onResume,
}: {
  item: ComeBackDeferred;
  resuming: boolean;
  onResume: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const canPreview = Boolean(item.statement_md);

  return (
    <li className="rounded-md border border-border bg-card px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium text-foreground">{item.title}</p>
          {item.topics.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {item.topics.map((slug) => (
                <Badge key={slug} variant="ghost" className="text-[10px]">
                  {slug.replace(/-/g, "‑")}
                </Badge>
              ))}
            </div>
          )}
          {item.deferred_at && (
            <p className="mt-2 text-xs text-muted-foreground">
              Set aside {fmt(item.deferred_at)}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <Button
            type="button"
            size="sm"
            disabled={resuming}
            onClick={onResume}
          >
            {resuming ? "Adding…" : "Queue it now"}
          </Button>
          {canPreview && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-[var(--forest)] underline-offset-2 hover:underline"
            >
              {expanded ? "Hide preview" : "Preview"}
            </button>
          )}
        </div>
      </div>

      {expanded && canPreview && (
        <div className="mt-4 border-t border-border pt-4">
          {item.context_md && (
            <div className="mb-4 border-l-2 border-amber pl-4">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Context
              </p>
              <div className="font-serif text-sm leading-[1.7] text-muted-foreground [&_p]:mb-2 [&_p:last-child]:mb-0">
                <MarkdownLatex source={item.context_md} />
              </div>
            </div>
          )}
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Problem
          </p>
          <div className="font-serif text-sm leading-[1.7] text-foreground [&_p]:mb-3 [&_p:last-child]:mb-0 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-1.5">
            <MarkdownLatex source={item.statement_md ?? ""} />
          </div>
        </div>
      )}
    </li>
  );
}
