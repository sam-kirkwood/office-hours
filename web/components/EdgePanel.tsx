"use client";

import { useEffect, useState } from "react";
import MarkdownLatex from "@/lib/markdown";
import type { Edge, Node } from "@/lib/types";

interface Props {
  edge: Edge;
  sourceNode: Node | undefined;
  targetNode: Node | undefined;
  onClose: () => void;
}

const KIND_LABEL: Record<Edge["edge_kind"], string> = {
  prerequisite: "Prerequisite",
  related: "Related",
};

interface EdgeDescriptionResponse {
  description_md?: string;
  cached?: boolean;
  error?: string;
}

export default function EdgePanel({ edge, sourceNode, targetNode, onClose }: Props) {
  const [description, setDescription] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDescription(null);
    setLoading(true);
    setError(null);
    fetch(`/api/edge/${edge.id}/description`)
      .then((r) => r.json())
      .then((data: EdgeDescriptionResponse) => {
        if (cancelled) return;
        if (data.description_md) {
          setDescription(data.description_md);
        } else {
          setError(data.error ?? "Couldn't load description.");
        }
      })
      .catch(() => {
        if (cancelled) return;
        setError("Couldn't load description.");
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [edge.id]);

  return (
    <div className="absolute right-0 top-0 z-10 flex h-full w-80 flex-col border-l border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="truncate font-semibold text-foreground">
          {sourceNode?.title ?? "?"} → {targetNode?.title ?? "?"}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="ml-2 shrink-0 text-muted-foreground transition-colors duration-[var(--duration-fast)] hover:text-foreground"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
          {KIND_LABEL[edge.edge_kind]}
        </p>
        {loading && (
          <p className="font-serif text-sm italic text-muted-foreground">
            Drawing the connection…
          </p>
        )}
        {!loading && description && (
          <div
            className={`font-serif text-sm leading-[1.7] text-foreground
              [&_p]:mb-3 [&_p:last-child]:mb-0
              [&_strong]:font-semibold [&_em]:italic
              [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded`}
          >
            <MarkdownLatex source={description} />
          </div>
        )}
        {!loading && !description && error && (
          <p className="text-sm text-muted-foreground">{error}</p>
        )}
      </div>
    </div>
  );
}
