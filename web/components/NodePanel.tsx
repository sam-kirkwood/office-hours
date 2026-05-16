"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import MarkdownLatex from "@/lib/markdown";
import type { Node, UserNodeState } from "@/lib/types";

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

export default function NodePanel({ node, state, isUserNode, onClose }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGetProblem() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/queue/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_id: node.id }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed");
      router.push(`/problem/${data.queue_item_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setLoading(false);
    }
  }

  async function handleAddInterest() {
    setAdding(true);
    setError(null);
    try {
      const res = await fetch("/api/interest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: node.title }),
      });
      if (!res.ok) throw new Error("Failed to add interest");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setAdding(false);
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

        {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

        <div className="flex flex-col gap-2">
          <Button
            type="button"
            onClick={handleGetProblem}
            disabled={loading}
            className="w-full"
          >
            {loading ? "Generating…" : "Get a problem"}
          </Button>

          {!isUserNode && (
            <Button
              type="button"
              variant="outline"
              onClick={handleAddInterest}
              disabled={adding}
              className="w-full"
            >
              {adding ? "Adding…" : "Add to my interests"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
