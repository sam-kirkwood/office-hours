"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";

interface QueueItem {
  id: string;
  kind: string;
  state: string;
  priority_score: number | null;
  added_reason: string | null;
  node_title: string | null;
}

interface UserQueueCardProps {
  userId: string;
  email: string;
  displayName: string | null;
  createdAt: string;
  interestCount: number;
  initialQueue: QueueItem[];
}

const STATE_COLOURS: Record<string, string> = {
  pending: "text-muted-foreground",
  surfaced: "text-[var(--amber)]",
  in_progress: "text-[var(--amber)] font-medium",
  done: "text-[var(--forest)]",
  skipped: "text-muted-foreground/60",
};

function KindBadge({ kind }: { kind: string }) {
  switch (kind) {
    case "problem":
      return <Badge variant="default" className="text-[10px] shrink-0">problem</Badge>;
    case "paper_engagement":
      return <Badge variant="secondary" className="text-[10px] shrink-0">paper</Badge>;
    case "refresher":
      return (
        <Badge variant="outline" className="border-[var(--forest)] text-[var(--forest)] text-[10px] shrink-0">
          refresher
        </Badge>
      );
    case "suggested_interest":
      return <Badge variant="ghost" className="text-[10px] shrink-0">suggestion</Badge>;
    case "concept_review":
      return <Badge variant="outline" className="text-[10px] shrink-0">concept</Badge>;
    default:
      return <Badge variant="outline" className="text-[10px] shrink-0">{kind}</Badge>;
  }
}

export function UserQueueCard({
  email,
  displayName,
  createdAt,
  interestCount,
  initialQueue,
}: UserQueueCardProps) {
  const [open, setOpen] = useState(false);
  const [queue, setQueue] = useState<QueueItem[]>(initialQueue);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleDelete(itemId: string) {
    setDeleting(itemId);
    try {
      const res = await fetch(`/api/admin/queue/${itemId}`, { method: "DELETE" });
      if (res.ok) setQueue((prev) => prev.filter((qi) => qi.id !== itemId));
    } finally {
      setDeleting(null);
    }
  }

  const joinDate = new Date(createdAt).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="rounded-md border border-border bg-card">
      {/* Header — always visible, click to toggle */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-baseline gap-3 min-w-0">
          <span className="font-mono text-sm text-foreground truncate">{email}</span>
          {displayName && (
            <span className="text-xs text-muted-foreground shrink-0">{displayName}</span>
          )}
        </div>
        <div className="flex items-center gap-4 shrink-0 ml-4">
          <span className="text-xs text-muted-foreground">{interestCount} interests</span>
          <span className="text-xs text-muted-foreground">{queue.length} queued</span>
          <span className="text-xs text-muted-foreground">joined {joinDate}</span>
          <span className="text-xs text-muted-foreground select-none">{open ? "▾" : "▸"}</span>
        </div>
      </button>

      {/* Queue table — collapsible */}
      {open && (
        <div className="border-t border-border">
          {queue.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground/60">Empty queue.</p>
          ) : (
            <table className="w-full table-fixed">
              <colgroup>
                <col className="w-28" />
                <col className="w-24" />
                <col />
                <col className="w-16" />
                <col className="w-8" />
              </colgroup>
              <thead>
                <tr className="border-b border-border/40">
                  <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Kind</th>
                  <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">State</th>
                  <th className="px-4 py-2 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Topic / reason</th>
                  <th className="px-4 py-2 text-right text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Priority</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {queue.map((qi) => {
                  const label = qi.node_title ?? qi.added_reason ?? "—";
                  return (
                    <tr key={qi.id} className="border-b border-border/30 last:border-0">
                      <td className="px-4 py-2"><KindBadge kind={qi.kind} /></td>
                      <td className="px-4 py-2">
                        <span className={`text-xs ${STATE_COLOURS[qi.state] ?? "text-muted-foreground"}`}>
                          {qi.state}
                        </span>
                      </td>
                      <td className="px-4 py-2 overflow-hidden">
                        <span
                          className="block truncate text-xs text-muted-foreground"
                          title={label}
                        >
                          {label}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-xs text-muted-foreground">
                        {qi.priority_score != null ? Number(qi.priority_score).toFixed(2) : "—"}
                      </td>
                      <td className="pr-3 py-2 text-center">
                        <button
                          type="button"
                          onClick={() => handleDelete(qi.id)}
                          disabled={deleting === qi.id}
                          className="text-muted-foreground/40 hover:text-destructive transition-colors text-xs leading-none disabled:opacity-40"
                          title="Remove from queue"
                        >
                          ×
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
