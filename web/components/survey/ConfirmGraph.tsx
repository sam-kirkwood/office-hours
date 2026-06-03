"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import SkillTreeView from "@/components/SkillTreeView";
import SurveyNodePanel from "@/components/survey/SurveyNodePanel";
import DialogModal from "@/components/addInterest/DialogModal";
import { useIsMobile } from "@/lib/useIsMobile";
import type { Node, Edge, UserNodeState } from "@/lib/types";

export interface GraphSlice {
  user_nodes: Array<{ node: Node; state: UserNodeState | null }>;
  adjacent_nodes: Node[];
  edges: Edge[];
}

interface Props {
  initialGraphData: GraphSlice;
  interestNodeIds: string[];
}

// Stage 7 confirmation legend — deliberately simpler than the post-onboarding
// skill tree's. The survey context only needs the user to recognise "these
// are mine" vs "these are nearby"; engagement-derived states like struggling
// have no place here (we just collected onboarding signal — they can't have
// been earned yet) and exposing them would also break the no-guilt principle.
function ConfirmLegend() {
  return (
    <div className="absolute bottom-4 left-4 z-10 rounded-md border border-border bg-card px-3.5 py-3">
      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        Legend
      </p>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 rounded-full border-2 border-primary bg-[var(--amber-subtle)]" />
          <span className="text-[11px] text-muted-foreground">
            Your interests &amp; foundations to refresh
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 rounded-full border border-dashed border-border/50 bg-background" />
          <span className="text-[11px] text-muted-foreground">Nearby</span>
        </div>
      </div>
    </div>
  );
}

export default function ConfirmGraph({ initialGraphData, interestNodeIds }: Props) {
  const router = useRouter();
  const isMobile = useIsMobile();
  const [graphData, setGraphData] = useState<GraphSlice>(initialGraphData);
  const [interestIdSet, setInterestIdSet] = useState<Set<string>>(
    new Set(interestNodeIds),
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloading, setReloading] = useState(false);

  // After a delete, refetch /api/graph/me so the layout reflects the change
  // and any nodes that became orphan-adjacent drop out. The deleted node id
  // is also removed from the local interest set immediately.
  const refreshGraph = useCallback(async (deletedNodeId?: string) => {
    if (deletedNodeId) {
      setInterestIdSet((prev) => {
        const next = new Set(prev);
        next.delete(deletedNodeId);
        return next;
      });
    }
    setReloading(true);
    try {
      const res = await fetch("/api/graph/me", { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to reload graph");
      const data = (await res.json()) as GraphSlice;
      setGraphData(data);
    } catch (err) {
      console.error("graph refresh failed:", err);
    } finally {
      setReloading(false);
    }
  }, []);

  // For Stage 7 we visually unify the user's interests with their marked
  // foundations — both are "things you said matter, in your queue". Without
  // this, interest nodes (which have no user_node_states row) render as
  // "unseen" / quiet card-bg, making them look less prominent than the
  // foundations the user just marked. We synthesise an "active" state for
  // any interest node missing one.
  const decoratedGraph = useMemo<GraphSlice>(() => {
    return {
      ...graphData,
      user_nodes: graphData.user_nodes.map((entry) => {
        if (entry.state || !interestIdSet.has(entry.node.id)) return entry;
        const synthetic: UserNodeState = {
          user_id: "",
          node_id: entry.node.id,
          state: "active",
          engagement_count: 0,
          struggle_score: 0,
          last_engaged_at: null,
        };
        return { ...entry, state: synthetic };
      }),
    };
  }, [graphData, interestIdSet]);

  // If the previous render's interest set was empty (no nodes yet) we still
  // want to show an explanation rather than an empty canvas.
  const hasContent =
    graphData.user_nodes.length > 0 || graphData.adjacent_nodes.length > 0;

  async function handleStart() {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey/complete", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Could not finish");
      }
      router.push("/daily");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finish");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col px-5 py-8">
      <div className="mb-4">
        <h1 className="font-serif text-2xl text-foreground">Here&apos;s what we&apos;ll start with.</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Your interests sit alongside the foundations they pull from. Tap any node to
          adjust — remove an interest you didn&apos;t mean to keep, or just have a look.
        </p>
        {reloading && (
          <p className="mt-2 text-xs italic text-muted-foreground">Refreshing…</p>
        )}
      </div>

      {isMobile ? (
        <ConfirmListView
          graphData={decoratedGraph}
          interestIdSet={interestIdSet}
          onChanged={(deletedNodeId) => refreshGraph(deletedNodeId)}
          hasContent={hasContent}
        />
      ) : (
        <div className="relative mb-6 h-[60vh] min-h-[420px] w-full overflow-hidden rounded-md border border-border bg-card">
          {hasContent ? (
            <SkillTreeView
              graphData={decoratedGraph}
              legend={<ConfirmLegend />}
              renderPanel={({ entry, onClose }) => (
                <SurveyNodePanel
                  node={entry.node}
                  state={entry.state}
                  isInterest={interestIdSet.has(entry.node.id)}
                  isFoundation={entry.node.kind === "foundation"}
                  onClose={onClose}
                  onDeleted={() => refreshGraph(entry.node.id)}
                  onEdited={() => refreshGraph()}
                />
              )}
            />
          ) : (
            <div className="flex h-full items-center justify-center px-6 text-center">
              <p className="text-sm text-muted-foreground">
                No interests landed yet — that&apos;s OK. You can add them from the daily view.
              </p>
            </div>
          )}
        </div>
      )}

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      <div className="flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/survey/balance")}
          disabled={submitting}
        >
          ← Back
        </Button>
        <Button type="button" onClick={handleStart} disabled={submitting} size="lg">
          {submitting ? "One moment…" : "Your queue is ready →"}
        </Button>
      </div>
    </div>
  );
}

// Mobile fallback for the Stage 7 confirmation. Renders interests +
// foundations + nearby as three list sections instead of the React-Flow
// canvas. Interest rows support Edit (opens DialogModal in preNode mode,
// pre-filled with the user's current intent_context) and Remove (DELETE
// /api/interest/[id]). Foundation + nearby rows are read-only.

interface ConfirmListViewProps {
  graphData: GraphSlice;
  interestIdSet: Set<string>;
  onChanged: (deletedNodeId?: string) => void;
  hasContent: boolean;
}

interface EditTarget {
  nodeId: string;
  nodeSlug: string;
  nodeTitle: string;
  currentIntent: string;
}

function ConfirmListView({
  graphData,
  interestIdSet,
  onChanged,
  hasContent,
}: ConfirmListViewProps) {
  const [editing, setEditing] = useState<EditTarget | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const { interests, foundations } = useMemo(() => {
    const interestRows: GraphSlice["user_nodes"] = [];
    const foundationRows: GraphSlice["user_nodes"] = [];
    for (const entry of graphData.user_nodes) {
      if (interestIdSet.has(entry.node.id)) interestRows.push(entry);
      else foundationRows.push(entry);
    }
    return { interests: interestRows, foundations: foundationRows };
  }, [graphData.user_nodes, interestIdSet]);

  async function handleEdit(node: Node) {
    setRowError(null);
    let currentIntent = "";
    try {
      const res = await fetch(
        `/api/interest/me?node_id=${encodeURIComponent(node.id)}`,
      );
      if (res.ok) {
        const data = (await res.json()) as { intent_context?: string };
        if (typeof data.intent_context === "string")
          currentIntent = data.intent_context;
      }
    } catch {
      /* swallow — dialog still works without prefill */
    }
    setEditing({
      nodeId: node.id,
      nodeSlug: node.slug,
      nodeTitle: node.title,
      currentIntent,
    });
  }

  async function handleDelete(node: Node) {
    if (!confirm(`Remove "${node.title}" from your interests?`)) return;
    setBusy(node.id);
    setRowError(null);
    try {
      const res = await fetch(`/api/interest/${node.id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Delete failed");
      }
      onChanged(node.id);
    } catch (err) {
      setRowError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(null);
    }
  }

  if (!hasContent) {
    return (
      <div className="mb-6 rounded-md border border-dashed border-border bg-card/50 px-5 py-10 text-center">
        <p className="text-sm text-muted-foreground">
          No interests landed yet — that&apos;s OK. You can add them from the
          daily view.
        </p>
      </div>
    );
  }

  return (
    <div className="mb-6 space-y-6">
      {rowError && <p className="text-sm text-destructive">{rowError}</p>}

      {interests.length > 0 && (
        <ConfirmListSection title="Your interests">
          <ul className="space-y-3">
            {interests.map(({ node }) => (
              <li
                key={node.id}
                className="rounded-md border border-primary/40 bg-[var(--amber-subtle)] p-4"
              >
                <p className="font-serif text-base text-foreground">
                  {node.title}
                </p>
                <ConfirmIntentLine nodeId={node.id} />
                <div className="mt-3 flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => handleEdit(node)}
                  >
                    Edit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(node)}
                    disabled={busy === node.id}
                  >
                    {busy === node.id ? "Removing…" : "Remove"}
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </ConfirmListSection>
      )}

      {foundations.length > 0 && (
        <ConfirmListSection title="Foundations to refresh">
          <ul className="space-y-3">
            {foundations.map(({ node }) => (
              <li
                key={node.id}
                className="rounded-md border border-border bg-card p-4"
              >
                <p className="font-serif text-base text-foreground">
                  {node.title}
                </p>
                <ConfirmShortDescription md={node.description_md} />
              </li>
            ))}
          </ul>
        </ConfirmListSection>
      )}

      {graphData.adjacent_nodes.length > 0 && (
        <ConfirmListSection title="Nearby">
          <ul className="space-y-3">
            {graphData.adjacent_nodes.map((node) => (
              <li
                key={node.id}
                className="rounded-md border border-dashed border-border/60 bg-background p-4"
              >
                <p className="font-serif text-base text-muted-foreground">
                  {node.title}
                </p>
                <ConfirmShortDescription md={node.description_md} muted />
              </li>
            ))}
          </ul>
        </ConfirmListSection>
      )}

      {editing && (
        <DialogModal
          open={true}
          onOpenChange={(o) => !o && setEditing(null)}
          mode="preNode"
          preNode={{
            slug: editing.nodeSlug,
            title: editing.nodeTitle,
            defaultIntentContext: editing.currentIntent,
            mirrorOverride: `Editing ${editing.nodeTitle}.`,
            followupPromptOverride: "What's off, or what would you change?",
          }}
          addedVia="survey"
          title={`Edit ${editing.nodeTitle}`}
          onComplete={() => {
            setEditing(null);
            onChanged();
          }}
        />
      )}
    </div>
  );
}

function ConfirmListSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ConfirmShortDescription({
  md,
  muted = false,
}: {
  md: string | null | undefined;
  muted?: boolean;
}) {
  if (!md) return null;
  const line = md
    .replace(/[*_`#]/g, "")
    .split("\n")
    .find((s) => s.trim().length > 0)
    ?.trim();
  if (!line) return null;
  return (
    <p
      className={`mt-1 text-sm leading-relaxed ${muted ? "text-muted-foreground/80" : "text-muted-foreground"}`}
    >
      {line}
    </p>
  );
}

// Fetches the user's intent_context for an interest node and renders it
// inline. Kept as a tiny per-row fetcher rather than batched because the
// confirm view's interest list is typically 1-5 rows — within the noise
// floor for an extra Postgres roundtrip per row.
function ConfirmIntentLine({ nodeId }: { nodeId: string }) {
  const [intent, setIntent] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/interest/me?node_id=${encodeURIComponent(nodeId)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { intent_context?: string } | null) => {
        if (cancelled) return;
        if (data && typeof data.intent_context === "string") {
          setIntent(data.intent_context.trim() || null);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [nodeId]);

  if (!intent) return null;
  return (
    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
      {intent}
    </p>
  );
}
