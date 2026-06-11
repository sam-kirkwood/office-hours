"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import MarkdownLatex from "@/lib/markdown";
import { optimisticQueueRequest, queueItemPath } from "@/lib/optimisticQueueRequest";
import type { OrientingConcept } from "@/lib/types";

interface Props {
  concepts: (string | OrientingConcept)[];
  // The paper engagement's queue_item_id, recorded as the parent on any
  // refresher/concept_review created from a term click so the resulting
  // reading view can offer a back-link to this paper.
  parentQueueItemId?: string;
}

function normalize(c: string | OrientingConcept): OrientingConcept {
  if (typeof c === "string") return { term: c, definition_md: "" };
  return { term: c.term, definition_md: c.definition_md ?? "" };
}

export default function OrientingConceptsPanel({ concepts, parentQueueItemId }: Props) {
  const router = useRouter();
  const [openTerm, setOpenTerm] = useState<string | null>(null);
  const [requesting, setRequesting] = useState<string | null>(null);

  const normalized = concepts.map(normalize);

  function handleToggle(term: string) {
    setOpenTerm((cur) => (cur === term ? null : term));
  }

  function handleRefresher(term: string) {
    setRequesting(term);
    optimisticQueueRequest({
      body: {
        raw_text: term,
        kind_hint: "refresher",
        parent_queue_item_id: parentQueueItemId,
      },
      // A refresher request resolves to a concrete kind (problem /
      // concept_review / paper_engagement); route by it.
      targetPath: queueItemPath,
      router,
      labels: {
        pending: `Lining up a refresher on ${term}…`,
        queued: "Added to your queue.",
      },
    })
      .catch(() => {/* surfaced via toast */})
      .finally(() => setRequesting(null));
  }

  if (normalized.length === 0) return null;

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Orienting concepts
      </p>
      <div className="flex flex-wrap gap-2">
        {normalized.map((concept) => {
          const isOpen = openTerm === concept.term;
          const hasDefinition = concept.definition_md.length > 0;
          return (
            <button
              key={concept.term}
              type="button"
              onClick={() => hasDefinition && handleToggle(concept.term)}
              disabled={!hasDefinition}
              className={`rounded-full border px-3 py-1 font-serif text-xs transition-colors duration-[var(--duration-fast)] ${
                isOpen
                  ? "border-[var(--forest)] bg-[var(--forest-subtle)] text-foreground"
                  : "border-border text-foreground hover:border-[var(--forest)]/50"
              } ${hasDefinition ? "cursor-pointer" : "cursor-default opacity-80"}`}
              aria-expanded={hasDefinition ? isOpen : undefined}
            >
              {concept.term}
            </button>
          );
        })}
      </div>

      {openTerm && (() => {
        const concept = normalized.find((c) => c.term === openTerm);
        if (!concept || !concept.definition_md) return null;
        return (
          <div
            className="mt-3 max-w-prose rounded-md border border-[var(--forest)]/30 bg-[var(--forest-subtle)] px-4 py-3.5
              transition-[opacity,transform] duration-[var(--duration-standard)] [transition-timing-function:var(--ease-expressive)]"
          >
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--forest)]">
              {concept.term}
            </p>
            <div className="font-serif text-sm leading-[1.7] text-foreground
              [&_p]:mb-2 [&_p:last-child]:mb-0
              [&_strong]:font-semibold [&_em]:italic
              [&_code]:font-mono [&_code]:text-xs [&_code]:bg-background [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded">
              <MarkdownLatex source={concept.definition_md} />
            </div>
            <div className="mt-3.5 border-t border-[var(--forest)]/15 pt-3">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => handleRefresher(concept.term)}
                disabled={requesting === concept.term}
                className="border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest-subtle)]"
              >
                {requesting === concept.term ? "Lining up…" : "Get a refresher on this"}
              </Button>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
