"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import MarkdownLatex from "@/lib/markdown";
import type { ConceptReviewNodeReading } from "@/lib/pythonApi";

interface Props {
  queueItemId: string;
  node: ConceptReviewNodeReading;
  // Set when this concept review was triggered from inside another surface
  // (currently only paper engagements). Drives the top-of-page back-link so
  // the user can return to where they came from.
  parentPaper?: { queue_item_id: string; paper_title: string } | null;
}

export default function ConceptReadingView({ queueItemId, node, parentPaper }: Props) {
  const router = useRouter();
  const [marking, setMarking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleMarkDone() {
    setMarking(true);
    setError(null);
    try {
      const res = await fetch(`/api/concept-review/${queueItemId}/done`, {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? "Couldn't mark done");
      }
      // If the user came here from a paper, return to it. Otherwise back to daily.
      router.push(parentPaper ? `/paper/${parentPaper.queue_item_id}` : "/daily");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't mark done");
      setMarking(false);
    }
  }

  const subtopics = node.subtopics_json ?? [];
  const readingClass = `font-serif text-base leading-[1.7] text-foreground
    [&_p]:mb-4 [&_p:last-child]:mb-0
    [&_strong]:font-semibold [&_em]:italic
    [&_code]:font-mono [&_code]:text-sm [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded`;

  return (
    <div className="mx-auto max-w-prose px-5 py-12">
      {parentPaper && (
        <Link
          href={`/paper/${parentPaper.queue_item_id}`}
          className="mb-6 inline-block text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
        >
          ← Back to {parentPaper.paper_title}
        </Link>
      )}
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Concept
      </p>
      <h1 className="mb-6 font-serif text-2xl font-semibold text-foreground">
        {node.title}
      </h1>

      {/* Brief takes precedence over description_md when present — it's the
          generated reading surface. description_md is shown only as a fallback
          if brief generation failed. */}
      {node.brief_md ? (
        <div className={readingClass}>
          <MarkdownLatex source={node.brief_md} />
        </div>
      ) : (
        node.description_md && (
          <div className={readingClass}>
            <MarkdownLatex source={node.description_md} />
          </div>
        )
      )}

      {subtopics.length > 0 && (
        <div className="mt-10">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Subtopics
          </h2>
          <dl className="space-y-4 font-serif text-base leading-[1.7] text-foreground">
            {subtopics.map((s) => (
              <div key={s.slug}>
                <dt className="font-medium text-foreground">{s.title}</dt>
                {s.gloss_md && (
                  <dd className="mt-0.5 text-sm text-muted-foreground leading-[1.7]
                    [&_p]:mb-2 [&_p:last-child]:mb-0
                    [&_strong]:font-semibold [&_em]:italic
                    [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded">
                    <MarkdownLatex source={s.gloss_md} />
                  </dd>
                )}
              </div>
            ))}
          </dl>
        </div>
      )}

      {error && <p className="mt-6 text-sm text-destructive">{error}</p>}

      <div className="mt-10 flex items-center gap-3">
        <Button onClick={handleMarkDone} disabled={marking}>
          {marking ? "Saving…" : "I've looked through this"}
        </Button>
        <Link
          href="/daily"
          className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)]"
        >
          Back to daily
        </Link>
      </div>
    </div>
  );
}
