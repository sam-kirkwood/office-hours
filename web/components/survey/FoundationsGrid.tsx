"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Node } from "@/lib/types";

interface Props {
  foundationNodes: Node[];
  initialRefreshSlugs: string[];
  relationshipCards: string[]; // drives label framing per §1.3.4
  foregroundDomains: string[]; // domains highlighted from Stage 1 chips
}

const DOMAIN_LABELS: Record<string, string> = {
  math: "Mathematics",
  physics: "Physics",
  applied: "Applied",
};

const DIFFICULTY_ORDER: Record<string, number> = { intro: 0, core: 1, advanced: 2 };

function describeLabel(relationshipCards: string[]): { marked: string; unmarked: string } {
  const isCurious =
    relationshipCards.length === 1 && relationshipCards[0] === "curious";
  if (isCurious) {
    return { marked: "New to this", unmarked: "Know this? Tap to flag as new." };
  }
  return {
    marked: "Want to refresh",
    unmarked: "Comfortable with this? Tap to flag as refresh.",
  };
}

export default function FoundationsGrid({
  foundationNodes,
  initialRefreshSlugs,
  relationshipCards,
  foregroundDomains,
}: Props) {
  const router = useRouter();
  const [marked, setMarked] = useState<Set<string>>(new Set(initialRefreshSlugs));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const labels = describeLabel(relationshipCards);

  const grouped = useMemo(() => {
    const byDomain: Record<string, Node[]> = {};
    for (const n of foundationNodes) {
      const key = n.domain ?? "applied";
      if (!byDomain[key]) byDomain[key] = [];
      byDomain[key].push(n);
    }
    for (const key of Object.keys(byDomain)) {
      byDomain[key].sort(
        (a, b) =>
          (DIFFICULTY_ORDER[a.difficulty_hint] ?? 9) - (DIFFICULTY_ORDER[b.difficulty_hint] ?? 9),
      );
    }
    const fg = foregroundDomains.length > 0 ? foregroundDomains : Object.keys(byDomain);
    const foreground = fg.filter((d) => byDomain[d]);
    const background = Object.keys(byDomain).filter((d) => !foreground.includes(d));
    return { byDomain, foreground, background };
  }, [foundationNodes, foregroundDomains]);

  function toggle(slug: string) {
    setMarked((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  async function submit(continueTo: "/survey/interests") {
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/survey/foundations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_slugs: Array.from(marked) }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? "Save failed");
      }
      router.push(continueTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <div className="mb-6">
        <h1 className="font-serif text-2xl text-foreground">Which foundations would you like to revisit?</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Tap any topic you&apos;d like to brush up on. Skip if none jump out — we&apos;ll calibrate as we go.
        </p>
      </div>

      {grouped.foreground.map((domain) => (
        <DomainSection
          key={domain}
          domain={domain}
          emphasis="primary"
          nodes={grouped.byDomain[domain]}
          marked={marked}
          onToggle={toggle}
          markedLabel={labels.marked}
          unmarkedLabel={labels.unmarked}
        />
      ))}
      {grouped.background.map((domain) => (
        <DomainSection
          key={domain}
          domain={domain}
          emphasis="quiet"
          nodes={grouped.byDomain[domain]}
          marked={marked}
          onToggle={toggle}
          markedLabel={labels.marked}
          unmarkedLabel={labels.unmarked}
        />
      ))}

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

      <div className="mt-10 flex justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.push("/survey/background")}
          disabled={submitting}
        >
          ← Back
        </Button>
        <Button type="button" onClick={() => submit("/survey/interests")} disabled={submitting} size="lg">
          {submitting ? "Saving…" : marked.size === 0 ? "Skip this step →" : "Continue →"}
        </Button>
      </div>
    </div>
  );
}

function DomainSection({
  domain,
  emphasis,
  nodes,
  marked,
  onToggle,
  markedLabel,
  unmarkedLabel,
}: {
  domain: string;
  emphasis: "primary" | "quiet";
  nodes: Node[];
  marked: Set<string>;
  onToggle: (slug: string) => void;
  markedLabel: string;
  unmarkedLabel: string;
}) {
  if (!nodes || nodes.length === 0) return null;
  return (
    <section className={emphasis === "quiet" ? "mb-8 opacity-80" : "mb-8"}>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {DOMAIN_LABELS[domain] ?? domain}
        {emphasis === "quiet" && (
          <span className="ml-2 normal-case font-normal text-muted-foreground/70">
            (not in your selected areas — included for completeness)
          </span>
        )}
      </h2>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {nodes.map((node) => (
          <FoundationTile
            key={node.slug}
            node={node}
            isMarked={marked.has(node.slug)}
            onToggle={() => onToggle(node.slug)}
            markedLabel={markedLabel}
            unmarkedLabel={unmarkedLabel}
          />
        ))}
      </div>
    </section>
  );
}

function FoundationTile({
  node,
  isMarked,
  onToggle,
  markedLabel,
  unmarkedLabel,
}: {
  node: Node;
  isMarked: boolean;
  onToggle: () => void;
  markedLabel: string;
  unmarkedLabel: string;
}) {
  // One-line description: strip markdown and trim to a single line.
  const oneLine = (node.description_md ?? "")
    .replace(/[*_`#]/g, "")
    .split("\n")
    .find((s) => s.trim().length > 0)
    ?.trim();
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`flex flex-col gap-2 rounded-md border p-4 text-left transition-colors duration-[var(--duration-fast)] ${
        isMarked
          ? "border-primary bg-[var(--amber-subtle)]"
          : "border-border bg-card hover:border-foreground/30"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-serif text-sm text-foreground">{node.title}</p>
        <Badge variant="ghost" className="shrink-0 text-[10px]">
          {node.difficulty_hint}
        </Badge>
      </div>
      {oneLine && (
        <p className="line-clamp-2 text-sm text-muted-foreground">{oneLine}</p>
      )}
      <p
        className={`mt-auto text-xs uppercase tracking-widest ${
          isMarked ? "text-primary" : "text-muted-foreground/70"
        }`}
      >
        {isMarked ? `✓ ${markedLabel}` : unmarkedLabel}
      </p>
    </button>
  );
}
