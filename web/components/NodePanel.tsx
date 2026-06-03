"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import MarkdownLatex from "@/lib/markdown";
import { optimisticQueueRequest } from "@/lib/optimisticQueueRequest";
import type { Node, UserNodeState, NotebookEntry } from "@/lib/types";
import DialogModal from "@/components/addInterest/DialogModal";

interface SubtopicEntry {
  slug: string;
  title: string;
}

interface SubtopicGloss {
  slug: string;
  title?: string;
  gloss_md?: string;
}

interface SubtopicStateRow {
  subtopic_slug: string;
  state: "familiar" | "refresh" | "new";
}

const SUBTOPIC_STATE_LABEL: Record<SubtopicStateRow["state"], string> = {
  familiar: "Familiar",
  refresh: "Refresh",
  new: "Unseen",
};

// Foundation nodes carry [{slug, title}]; interest nodes carry string[]. The
// per-subtopic refresher action only makes sense for foundation subtopics
// (those are the keys both the concept tour and user_subtopic_states use),
// so we filter out the legacy string shape rather than try to render it.
function normalizeSubtopics(raw: unknown[]): SubtopicEntry[] {
  const out: SubtopicEntry[] = [];
  for (const item of raw) {
    if (
      item &&
      typeof item === "object" &&
      "slug" in item &&
      "title" in item &&
      typeof (item as { slug: unknown }).slug === "string" &&
      typeof (item as { title: unknown }).title === "string"
    ) {
      out.push({
        slug: (item as { slug: string }).slug,
        title: (item as { title: string }).title,
      });
    }
  }
  return out;
}

interface Props {
  node: Node;
  state: UserNodeState | null;
  isUserNode: boolean;
  onClose: () => void;
  // When set, NodePanel renders a Connected topics list. Clicking a row
  // swaps the panel to that neighbor by id.
  onSelectNode?: (nodeId: string) => void;
  // When set, NodePanel renders a "Highlight on canvas" button. The
  // callback receives the neighbor ids to ring + fit-view to.
  onHighlightNeighbors?: (neighborIds: string[]) => void;
}

interface NeighborEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_kind: "prerequisite" | "related";
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
  concept_review: "Concept",
};

export default function NodePanel({
  node,
  state,
  isUserNode,
  onClose,
  onSelectNode,
  onHighlightNeighbors,
}: Props) {
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
  const [subtopicStates, setSubtopicStates] = useState<Record<string, SubtopicStateRow["state"]>>({});
  const [subtopicGlosses, setSubtopicGlosses] = useState<Record<string, string>>({});
  const [requestingSubtopic, setRequestingSubtopic] = useState<string | null>(null);
  const [neighbors, setNeighbors] = useState<Node[]>([]);
  const [neighborEdges, setNeighborEdges] = useState<NeighborEdge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const subtopics = normalizeSubtopics(node.subtopics_json ?? []);
  const showSubtopics = node.kind === "foundation" && subtopics.length > 0;
  const showConnected = neighbors.length > 0 && (onSelectNode || onHighlightNeighbors);

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

  useEffect(() => {
    fetch(`/api/node/${node.id}/neighbors`)
      .then((r) => r.json())
      .then((data: { neighbors?: Node[]; edges?: NeighborEdge[] }) => {
        setNeighbors(data.neighbors ?? []);
        setNeighborEdges(data.edges ?? []);
      })
      .catch(() => {
        setNeighbors([]);
        setNeighborEdges([]);
      });
  }, [node.id]);

  useEffect(() => {
    if (!showSubtopics) {
      setSubtopicStates({});
      setSubtopicGlosses({});
      return;
    }
    fetch(`/api/node/${node.id}/subtopic-states`)
      .then((r) => r.json())
      .then((data: { states?: SubtopicStateRow[]; glosses?: SubtopicGloss[] }) => {
        const stateMap: Record<string, SubtopicStateRow["state"]> = {};
        for (const row of data.states ?? []) {
          stateMap[row.subtopic_slug] = row.state;
        }
        setSubtopicStates(stateMap);
        const glossMap: Record<string, string> = {};
        for (const g of data.glosses ?? []) {
          if (g.slug && g.gloss_md) glossMap[g.slug] = g.gloss_md;
        }
        setSubtopicGlosses(glossMap);
      })
      .catch(() => {
        setSubtopicStates({});
        setSubtopicGlosses({});
      });
  }, [node.id, showSubtopics]);

  function handleSubtopicRefresher(subtopic: SubtopicEntry) {
    setRequestingSubtopic(subtopic.slug);
    setError(null);
    setInfo(null);
    optimisticQueueRequest({
      body: { raw_text: subtopic.title, kind_hint: "refresher" },
      // A subtopic-level refresher resolves to a concept_review on the parent
      // foundation node (Step 5 fallback path), since the user typically has
      // no notebook history at subtopic granularity.
      targetPath: (id, kind) =>
        kind === "concept_review" ? `/concept-review/${id}` : `/problem/${id}`,
      router,
      labels: {
        pending: `Lining up a refresher on ${subtopic.title}…`,
        queued: "Added to your queue.",
      },
    })
      .catch(() => {/* surfaced via toast */})
      .finally(() => setRequestingSubtopic(null));
  }

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

        {showSubtopics && (
          <div className="mb-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Subtopics
            </p>
            <ul className="space-y-3">
              {subtopics.map((subtopic) => {
                const subState = subtopicStates[subtopic.slug];
                const gloss = subtopicGlosses[subtopic.slug];
                const isRequesting = requestingSubtopic === subtopic.slug;
                return (
                  <li key={subtopic.slug}>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="font-serif text-sm text-foreground">
                        {subtopic.title}
                      </span>
                      {subState && (
                        <span className="shrink-0 text-[10px] uppercase tracking-widest text-muted-foreground">
                          {SUBTOPIC_STATE_LABEL[subState]}
                        </span>
                      )}
                    </div>
                    {gloss && (
                      <p className="mt-1 font-serif text-xs leading-relaxed text-muted-foreground">
                        {gloss}
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={() => handleSubtopicRefresher(subtopic)}
                      disabled={isRequesting}
                      className="mt-1.5 text-xs text-[var(--forest)] underline-offset-2 transition-colors duration-[var(--duration-fast)] hover:underline disabled:opacity-60"
                    >
                      {isRequesting ? "Lining up…" : "Request a refresher"}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {showConnected && (
          <div className="mb-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Connected topics
            </p>
            <ul className="space-y-1">
              {neighbors.map((n) => {
                const edge = neighborEdges.find(
                  (e) =>
                    (e.source_node_id === node.id && e.target_node_id === n.id) ||
                    (e.target_node_id === node.id && e.source_node_id === n.id),
                );
                const kindHint =
                  edge?.edge_kind === "prerequisite"
                    ? edge.source_node_id === node.id
                      ? "unlocks"
                      : "prereq"
                    : "related";
                return (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => onSelectNode?.(n.id)}
                      disabled={!onSelectNode}
                      className="group flex w-full items-baseline justify-between gap-2 rounded px-1 py-0.5 text-left transition-colors duration-[var(--duration-fast)] hover:bg-muted disabled:cursor-default disabled:hover:bg-transparent"
                    >
                      <span className="truncate font-serif text-sm text-foreground">
                        {n.title}
                      </span>
                      <span className="shrink-0 text-[10px] uppercase tracking-widest text-muted-foreground">
                        {kindHint}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {onHighlightNeighbors && (
              <button
                type="button"
                onClick={() => onHighlightNeighbors(neighbors.map((n) => n.id))}
                className="mt-2 text-xs text-[var(--forest)] underline-offset-2 transition-colors duration-[var(--duration-fast)] hover:underline"
              >
                Highlight on canvas
              </button>
            )}
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

          {/* S8 — A bookmarked, not-yet-interest node is a deliberate
              "come back to this" signal. Hoist promotion to a primary CTA
              right under "Get a problem" so the forward path is unmissable. */}
          {!isUserNode && (bookmarked || state?.state === "bookmarked") && (
            <Button
              type="button"
              onClick={openAddDialog}
              className="w-full"
            >
              Promote to interest
            </Button>
          )}

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

          {!isUserNode && !(bookmarked || state?.state === "bookmarked") && (
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
