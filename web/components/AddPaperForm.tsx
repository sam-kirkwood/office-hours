"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function AddPaperForm() {
  const [expanded, setExpanded] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [added, setAdded] = useState<{ queueItemId: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/paper/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: input.trim() }),
      });
      const data = (await res.json()) as { queue_item_id?: string; error?: string };
      if (!res.ok) throw new Error(data.error ?? "Failed to add paper");
      setAdded({ queueItemId: data.queue_item_id! });
      setInput("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add paper");
    } finally {
      setLoading(false);
    }
  }

  if (added) {
    return (
      <p className="text-sm text-muted-foreground">
        Added! It&apos;s in your queue.{" "}
        <Link
          href={`/paper/${added.queueItemId}`}
          className="text-[var(--amber)] underline underline-offset-2"
        >
          Open it →
        </Link>
      </p>
    );
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="text-sm text-muted-foreground underline-offset-2 hover:text-foreground hover:underline transition-colors duration-[var(--duration-fast)]"
      >
        Found a paper? Add it →
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <Input
        type="text"
        placeholder="Paste an arXiv URL, DOI, or title"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={loading}
        autoFocus
      />
      <div className="flex items-center gap-3">
        <Button type="submit" size="sm" disabled={loading || !input.trim()}>
          {loading ? "Adding…" : "Add paper"}
        </Button>
        <button
          type="button"
          onClick={() => {
            setExpanded(false);
            setError(null);
          }}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
        >
          Cancel
        </button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </form>
  );
}
