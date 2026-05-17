"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

type KindHint = "problem" | "paper" | "refresher";

interface RequestResponse {
  queue_item_id: string | null;
  kind: string;
  message?: string;
  error?: string;
}

export default function RequestBox() {
  const [expanded, setExpanded] = useState(false);
  const [text, setText] = useState("");
  const [kindHint, setKindHint] = useState<KindHint>("problem");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      const res = await fetch("/api/queue/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: text.trim(), kind_hint: kindHint }),
      });
      const data = (await res.json()) as RequestResponse;
      if (!res.ok) throw new Error(data.error ?? "Request failed");

      if (data.queue_item_id) {
        const path =
          data.kind === "paper_engagement"
            ? `/paper/${data.queue_item_id}`
            : `/problem/${data.queue_item_id}`;
        router.push(path);
      } else {
        setMessage(data.message ?? "Added to your queue.");
        setText("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)]"
      >
        Request something specific →
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-2">
        {(["problem", "paper", "refresher"] as KindHint[]).map((k) => (
          <button
            key={k}
            type="button"
            onClick={() => setKindHint(k)}
            className={`px-2.5 py-1 rounded text-xs border transition-colors duration-[var(--duration-fast)] ${
              kindHint === k
                ? "border-[var(--primary)] bg-[var(--amber-subtle)] text-foreground font-medium"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {k.charAt(0).toUpperCase() + k.slice(1)}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            kindHint === "paper"
              ? "e.g. LIGO, neural networks, topology"
              : kindHint === "refresher"
              ? "e.g. contour integration, Fourier series"
              : "e.g. complex analysis, differential equations"
          }
          className="flex-1 rounded border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--primary)] placeholder:text-muted-foreground/60"
        />
        <Button type="submit" size="sm" disabled={loading || !text.trim()}>
          {loading ? "…" : "Go →"}
        </Button>
      </div>
      {message && (
        <p className="text-sm text-muted-foreground">{message}</p>
      )}
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
    </form>
  );
}
