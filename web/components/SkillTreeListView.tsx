"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import DialogModal from "@/components/addInterest/DialogModal";
import { optimisticQueueRequest } from "@/lib/optimisticQueueRequest";
import type { Node as AppNode, UserNodeState } from "@/lib/types";

// Mobile fallback for /skill-tree. ReactFlow at 375px viewport is unworkable
// (canvas occluded by the 320px NodePanel overlay), so on narrow viewports we
// render the same `graphData` shape as a list grouped by "yours" vs "nearby".
// Per the Phase 10-rev Step 7 handover: no EdgePanel, no "Connected topics",
// no "Highlight on canvas" — the list view stands on its own.

interface GraphData {
  user_nodes: Array<{ node: AppNode; state: UserNodeState | null; bookmarked?: boolean }>;
  adjacent_nodes: AppNode[];
}

interface Props {
  graphData: GraphData;
}

// "struggling" is internal (graph-design.md) and folds into "Active" so it
// never surfaces as a distinct, guilt-inducing state. Bookmarks are shown via a
// separate chip, not a state.
const STATE_LABELS: Record<UserNodeState["state"], string> = {
  unseen: "Unseen",
  bookmarked: "Active",
  active: "Active",
  struggling: "Active",
  comfortable: "Comfortable",
};

// Matches the state colour vocabulary from SkillTreeView's node styles, but
// flattened into a small Badge-style chip rather than a node border.
function stateBadgeClass(state: UserNodeState["state"]): string {
  switch (state) {
    case "comfortable":
      return "border-[var(--forest)]/50 bg-[var(--forest-subtle)] text-foreground";
    case "active":
    case "struggling":
    case "bookmarked":
      return "border-primary/50 bg-[var(--amber-subtle)] text-foreground";
    default:
      return "border-border bg-background text-muted-foreground";
  }
}

function oneLineDescription(md: string | null | undefined): string | null {
  if (!md) return null;
  const trimmed = md
    .replace(/[*_`#]/g, "")
    .split("\n")
    .find((s) => s.trim().length > 0)
    ?.trim();
  return trimmed ?? null;
}

export default function SkillTreeListView({ graphData }: Props) {
  const router = useRouter();
  const [pendingProblem, setPendingProblem] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState<AppNode | null>(null);

  function handleGetProblem(node: AppNode) {
    setPendingProblem(node.id);
    optimisticQueueRequest({
      body: { node_id: node.id },
      targetPath: (id) => `/problem/${id}`,
      router,
      labels: {
        pending: `Finding a problem on ${node.title}…`,
        queued: "Added to your queue.",
      },
    }).catch(() => {/* surfaced via toast */});
    setTimeout(() => setPendingProblem(null), 800);
  }

  const hasNothing =
    graphData.user_nodes.length === 0 && graphData.adjacent_nodes.length === 0;

  return (
    <div className="mx-auto max-w-2xl px-5 py-8">
      <header className="mb-6">
        <h1 className="font-serif text-2xl text-foreground">Your skill tree</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Tap a topic to pull up a problem or add a nearby one to your
          interests. View on a larger screen for the full graph.
        </p>
      </header>

      {hasNothing && (
        <div className="rounded-md border border-dashed border-border bg-card/50 px-5 py-10 text-center">
          <p className="text-sm font-medium text-foreground">No nodes yet.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Complete the survey to add interests to your graph.
          </p>
        </div>
      )}

      {graphData.user_nodes.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Your interests &amp; foundations
          </h2>
          <ul className="space-y-3">
            {graphData.user_nodes.map(({ node, state, bookmarked }) => {
              const description = oneLineDescription(node.description_md);
              const stateKey: UserNodeState["state"] = state?.state ?? "unseen";
              return (
                <li
                  key={node.id}
                  className="rounded-md border border-border bg-card p-4"
                >
                  <div className="mb-2 flex items-baseline justify-between gap-3">
                    <p className="font-serif text-base text-foreground">
                      {node.title}
                    </p>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {bookmarked && (
                        <span className="rounded border border-amber/50 bg-[var(--amber-subtle)] px-2 py-0.5 text-[10px] uppercase tracking-widest text-[var(--amber)]">
                          Saved
                        </span>
                      )}
                      {stateKey !== "unseen" && (
                        <span
                          className={`rounded border px-2 py-0.5 text-[10px] uppercase tracking-widest ${stateBadgeClass(stateKey)}`}
                        >
                          {STATE_LABELS[stateKey]}
                        </span>
                      )}
                    </div>
                  </div>
                  {description && (
                    <p className="mb-3 text-sm leading-relaxed text-muted-foreground">
                      {description}
                    </p>
                  )}
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => handleGetProblem(node)}
                    disabled={pendingProblem === node.id}
                    className="w-full"
                  >
                    {pendingProblem === node.id ? "Finding…" : "Get a problem"}
                  </Button>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {graphData.adjacent_nodes.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Nearby
          </h2>
          <ul className="space-y-3">
            {graphData.adjacent_nodes.map((node) => {
              const description = oneLineDescription(node.description_md);
              return (
                <li
                  key={node.id}
                  className="rounded-md border border-dashed border-border/60 bg-background p-4"
                >
                  <p className="mb-1 font-serif text-base text-muted-foreground">
                    {node.title}
                  </p>
                  {description && (
                    <p className="mb-3 text-sm leading-relaxed text-muted-foreground/80">
                      {description}
                    </p>
                  )}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setAddOpen(node)}
                    className="w-full"
                  >
                    Add to my interests
                  </Button>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {!hasNothing && (
        <p className="mt-8 text-center text-xs italic text-muted-foreground">
          View on desktop for the full graph.
        </p>
      )}

      {addOpen && (
        <DialogModal
          open={true}
          onOpenChange={(o) => !o && setAddOpen(null)}
          mode="preNode"
          preNode={{
            slug: addOpen.slug,
            title: addOpen.title,
            followupPromptOverride: "What draws you to this?",
          }}
          addedVia="explicit_request"
          title={`Add ${addOpen.title}`}
          onComplete={() => {
            setAddOpen(null);
            router.refresh();
          }}
        />
      )}
    </div>
  );
}
