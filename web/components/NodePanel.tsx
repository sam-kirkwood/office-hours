"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import MarkdownLatex from "@/lib/markdown";
import { optimisticQueueRequest } from "@/lib/optimisticQueueRequest";
import type { Node, UserNodeState, NotebookEntry } from "@/lib/types";
import DialogModal from "@/components/addInterest/DialogModal";

interface Props {
  node: Node;
  state: UserNodeState | null;
  isUserNode: boolean;
  onClose: () => void;
}

const DIFFICULTY_LABELS: Record<string, string> = {
  intro: "Intro",
  core: "Core",
  advanced: "Advanced",
};

const DOMAIN_LABELS: Record<string, string> = {
  math: "Math",
  physics: "Physics",
  applied: "Applied",
};

const STATE_LABELS: Record<string, string> = {
  unseen: "Unseen",
  bookmarked: "Bookmarked",
  active: "Active",
  struggling: "Struggling",
  comfortable: "Comfortable",
};

const ENTRY_KIND_LABELS: Record<string, string> = {
  problem_attempt: "Problem",
  paper_engagement: "Paper",
};

export default function NodePanel({ node, state, isUserNode, onClose }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [bookmarking, setBookmarking] = useState(false);
  const [bookmarked, setBookmarked] = useState(false);
  const [markingComfortable, setMarkingComfortable] = useState(false);
  const [comfortable, setComfortable] = useState(state?.state === "comfortable");
  const [requestingPaper, setRequestingPaper] = useState(false);
  const [history, setHistory] = useState<NotebookEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    setComfortable(state?.state === "comfortable");
    setBookmarked(false);
    setError(null);
    setInfo(null);
  }, [node.id, state?.state]);

  useEffect(() => {
    setHistoryLoading(true);
    fetch(`/api/notebook?topic=${encodeURIComponent(node.slug)}&limit=5`)
      .then((r) => r.json())
      .then((data) => setHistory(data.entries ?? []))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false));
  }, [node.slug]);

  function handleGetProblem() {
    setLoading(true);
    setError(null);
    setInfo(null);
    optimisticQueueRequest({
      body: { node_id: node.id },
      targetPath: (id) => `/problem/${id}`,
      router,
      labels: {
        pending: `Finding a problem on ${node.title}…`,
        queued: "Added to your queue.",
      },
    }).catch(() => {/* surfaced via toast */});
    // Brief debounce so the button can't be re-clicked while the toast is
    // still mounting. The toast carries success/error UI.
    setTimeout(() => setLoading(false), 800);
  }

  function openAddDialog() {
    setError(null);
    setInfo(null);
    setAddOpen(true);
  }

  async function handleBookmark() {
    setBookmarking(true);
    setError(null);
    setInfo(null);
    try {
      const res = await fetch(`/api/node/${node.id}/bookmark`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed");
      setBookmarked(data.bookmarked);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBookmarking(false);
    }
  }

  async function handleMarkComfortable() {
    setMarkingComfortable(true);
    setError(null);
    setInfo(null);
    try {
      const res = await fetch(`/api/node/${node.id}/comfortable`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error ?? "Failed");
      }
      setComfortable(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setMarkingComfortable(false);
    }
  }

  function handleRequestPaper() {
    setRequestingPaper(true);
    setError(null);
    setInfo(null);
    optimisticQueueRequest({
      body: { node_id: node.id, kind_hint: "paper" },
      targetPath: (id) => `/paper/${id}`,
      router,
      labels: {
        pending: `Finding a paper on ${node.title}…`,
        queued: "Adding a paper to your queue — it'll appear shortly.",
      },
    }).catch(() => {/* surfaced via toast */});
    setTimeout(() => setRequestingPaper(false), 800);
  }

  return (
    <div className="absolute right-0 top-0 z-10 flex h-full w-80 flex-col border-l border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="truncate font-semibold text-foreground">{node.title}</h2>
        <button
          type="button"
          onClick={onClose}
          className="ml-2 shrink-0 text-muted-foreground transition-colors duration-[var(--duration-fast)] hover:text-foreground"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="mb-4 flex flex-wrap gap-1.5">
          <Badge variant="ghost">
            {DOMAIN_LABELS[node.domain] ?? node.domain}
          </Badge>
          <Badge variant="ghost">
            {DIFFICULTY_LABELS[node.difficulty_hint] ?? node.difficulty_hint}
          </Badge>
          {state && (
            <Badge variant="ghost">
              {STATE_LABELS[state.state] ?? state.state}
            </Badge>
          )}
        </div>

        {node.description_md && (
          <div className={`mb-4 font-serif text-sm leading-relaxed text-foreground
            [&_p]:mb-3 [&_p:last-child]:mb-0
            [&_strong]:font-semibold [&_em]:italic
            [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded`}>
            <MarkdownLatex source={node.description_md} />
          </div>
        )}

        {node.unlocks_text && (
          <p className="mb-4 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Unlocks:</span> {node.unlocks_text}
          </p>
        )}

        {state && (
          <div className="mb-4 text-sm text-muted-foreground">
            {state.engagement_count > 0 && (
              <p>Engaged {state.engagement_count} time{state.engagement_count !== 1 ? "s" : ""}</p>
            )}
            {state.last_engaged_at && (
              <p>
                Last engaged:{" "}
                {new Date(state.last_engaged_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })}
              </p>
            )}
          </div>
        )}

        {!historyLoading && history.length > 0 && (
          <div className="mb-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Your history
            </p>
            <ul className="space-y-1.5">
              {history.map((entry) => (
                <li key={entry.id} className="text-sm">
                  <span className="mr-1.5 text-xs text-muted-foreground">
                    {ENTRY_KIND_LABELS[entry.entry_kind] ?? entry.entry_kind}
                  </span>
                  <span className="text-foreground">{entry.title}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
        {info && <p className="mb-3 text-sm text-muted-foreground">{info}</p>}

        <div className="flex flex-col gap-2">
          <Button
            type="button"
            onClick={handleGetProblem}
            disabled={loading}
            className="w-full"
          >
            {loading ? "Generating…" : "Get a problem"}
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={handleRequestPaper}
            disabled={requestingPaper}
            className="w-full"
          >
            {requestingPaper ? "Finding…" : "Request a paper"}
          </Button>

          <Button
            type="button"
            variant="outline"
            onClick={handleBookmark}
            disabled={bookmarking}
            className="w-full"
          >
            {bookmarking ? "Saving…" : bookmarked ? "Bookmarked ✓" : "Bookmark"}
          </Button>

          {!comfortable && (
            <Button
              type="button"
              variant="outline"
              onClick={handleMarkComfortable}
              disabled={markingComfortable}
              className="w-full"
            >
              {markingComfortable ? "Saving…" : "Mark as comfortable"}
            </Button>
          )}

          {!isUserNode && (
            <Button
              type="button"
              variant="outline"
              onClick={openAddDialog}
              className="w-full"
            >
              Add to my interests
            </Button>
          )}
        </div>
      </div>

      <DialogModal
        open={addOpen}
        onOpenChange={setAddOpen}
        mode="preNode"
        preNode={{
          slug: node.slug,
          title: node.title,
          followupPromptOverride: "What draws you to this?",
        }}
        addedVia="explicit_request"
        title={`Add ${node.title}`}
        onComplete={() => router.refresh()}
      />
    </div>
  );
}
