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
}

export default function ConceptReadingView({ queueItemId, node }: Props) {
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
      router.push("/daily");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't mark done");
      setMarking(false);
    }
  }

  const subtopics = node.subtopics_json ?? [];

  return (
    <div className="mx-auto max-w-prose px-5 py-12">
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Concept
      </p>
      <h1 className="mb-6 font-serif text-2xl font-semibold text-foreground">
        {node.title}
      </h1>

      {node.description_md && (
        <div className={`font-serif text-base leading-[1.7] text-foreground
          [&_p]:mb-4 [&_p:last-child]:mb-0
          [&_strong]:font-semibold [&_em]:italic
          [&_code]:font-mono [&_code]:text-sm [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded`}>
          <MarkdownLatex source={node.description_md} />
        </div>
      )}

      {subtopics.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Subtopics
          </h2>
          <ul className="space-y-1.5 font-serif text-base leading-[1.7] text-foreground">
            {subtopics.map((s) => (
              <li key={s.slug}>{s.title}</li>
            ))}
          </ul>
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
