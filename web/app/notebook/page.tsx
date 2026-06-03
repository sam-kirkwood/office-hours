"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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

export default function NotebookPage() {
  const [entries, setEntries] = useState<NotebookEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEntries = useCallback(async (search: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "20" });
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

  useEffect(() => { fetchEntries(""); }, [fetchEntries]);

  useEffect(() => {
    const t = setTimeout(() => fetchEntries(q), 300);
    return () => clearTimeout(t);
  }, [q, fetchEntries]);

  return (
    <div className="mx-auto max-w-2xl px-5 py-12">
      <div className="mb-8 flex items-baseline justify-between">
        <h1 className="text-xl font-semibold text-foreground">Notebook</h1>
        {!loading && (
          <span className="text-sm text-muted-foreground">
            {total} {total === 1 ? "entry" : "entries"}
          </span>
        )}
      </div>

      <Input
        type="search"
        placeholder="Search entries…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        className="mb-8"
      />

      {error && (
        <p className="mb-6 text-sm text-destructive">{error}</p>
      )}

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
      ) : entries.length === 0 ? (
        <div className="rounded-md border border-dashed border-border px-6 py-12 text-center">
          <p className="text-sm text-muted-foreground">
            {q
              ? "No entries match your search."
              : "No notebook entries yet. Complete a problem to create your first one."}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {entries.map((entry) => (
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
    </div>
  );
}
