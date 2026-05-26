"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import MarkdownLatex from "@/lib/markdown";
import type { Node, UserNodeState } from "@/lib/types";

interface Props {
  node: Node;
  state: UserNodeState | null;
  isInterest: boolean;       // user picked it as an interest in Stage 3/4
  isFoundation: boolean;     // node.kind === 'foundation'
  onClose: () => void;
  onDeleted: () => void;     // notify parent to refresh after a successful delete
}

const DOMAIN_LABELS: Record<string, string> = {
  math: "Math",
  physics: "Physics",
  applied: "Applied",
};

const DIFFICULTY_LABELS: Record<string, string> = {
  intro: "Intro",
  core: "Core",
  advanced: "Advanced",
};

// Survey-context panel for the Stage 7 confirmation
// (survey-and-difficulty-design.md §1.8.2). Interest nodes get Delete + Edit
// (Edit is stubbed for Step 2d when the add-interest dialog UI lands);
// foundation nodes are read-only.

export default function SurveyNodePanel({
  node,
  state,
  isInterest,
  isFoundation,
  onClose,
  onDeleted,
}: Props) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editStubVisible, setEditStubVisible] = useState(false);

  async function handleDelete() {
    if (!confirm(`Remove "${node.title}" from your interests?`)) return;
    setError(null);
    setDeleting(true);
    try {
      const res = await fetch(`/api/interest/${node.id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Delete failed");
      }
      onDeleted();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setDeleting(false);
    }
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
          <Badge variant="ghost">{DOMAIN_LABELS[node.domain] ?? node.domain}</Badge>
          <Badge variant="ghost">
            {DIFFICULTY_LABELS[node.difficulty_hint] ?? node.difficulty_hint}
          </Badge>
          {isFoundation && <Badge variant="outline">Foundation</Badge>}
          {isInterest && <Badge variant="default">Your interest</Badge>}
        </div>

        {node.description_md && (
          <div className="mb-4 font-serif text-sm leading-relaxed text-foreground [&_p]:mb-3 [&_p:last-child]:mb-0">
            <MarkdownLatex source={node.description_md} />
          </div>
        )}

        {isFoundation && (
          <p className="mb-4 text-sm text-muted-foreground">
            Foundation nodes are part of the shared graph and can&apos;t be removed from
            here — your relationship to them adjusts as you engage with content.
          </p>
        )}

        {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

        {isInterest && (
          <div className="flex flex-col gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setEditStubVisible((v) => !v)}
            >
              Edit
            </Button>
            {editStubVisible && (
              <p className="rounded-md border border-dashed border-border bg-card/60 p-3 text-xs text-muted-foreground">
                Editing an interest will open the add-interest conversation —
                that surface arrives in the next session. For now you can
                remove it and re-add it from the daily view later.
              </p>
            )}
            <Button
              type="button"
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? "Removing…" : "Delete"}
            </Button>
          </div>
        )}

        {state && state.engagement_count > 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            Engaged {state.engagement_count} time{state.engagement_count === 1 ? "" : "s"}
          </p>
        )}
      </div>
    </div>
  );
}
