"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import ModeBalanceControl from "@/components/ModeBalanceControl";
import DialogModal from "@/components/addInterest/DialogModal";

export interface QueuedItem {
  queue_item_id: string;
  kind: string;
  state: string;
  title: string;
  added_reason: string | null;
}

export interface ProfileInterest {
  user_interest_id: string;
  node_id: string;
  node_slug: string;
  node_title: string;
  intent_context: string;
  engagement_count: number;
  queued: QueuedItem[];
}

export interface ProfileFoundation {
  node_id: string;
  node_slug: string;
  node_title: string;
  domain: string;
  state: "unseen" | "bookmarked" | "active" | "struggling" | "comfortable";
  engagement_count: number;
}

interface Props {
  modeBalance: number;
  feedback: Record<string, boolean>;
  interests: ProfileInterest[];
  foundations: ProfileFoundation[];
}

const FEEDBACK_PROMPTS: { key: string; label: string }[] = [
  { key: "feedback_too_hard", label: "My problems are too hard" },
  { key: "feedback_assume_less", label: "Problems assume things I haven't seen" },
  { key: "feedback_more_papers", label: "I want more papers" },
  { key: "feedback_harder_problems", label: "I want harder problems" },
];

const STATE_LABELS: Record<ProfileFoundation["state"], string> = {
  unseen: "Unseen",
  bookmarked: "Bookmarked",
  active: "Refreshing",
  struggling: "Working through",
  comfortable: "Comfortable",
};

function stateBadgeClass(state: ProfileFoundation["state"]): string {
  switch (state) {
    case "comfortable":
      return "border-[var(--forest)]/50 bg-[var(--forest-subtle)] text-foreground";
    case "active":
      return "border-primary/50 bg-[var(--amber-subtle)] text-foreground";
    case "struggling":
      return "border-destructive/30 bg-destructive/[0.07] text-foreground";
    case "bookmarked":
      return "border-primary/40 bg-[var(--amber-subtle)] text-foreground";
    default:
      return "border-border bg-background text-muted-foreground";
  }
}

export default function ProfileView({
  modeBalance: initialModeBalance,
  feedback: initialFeedback,
  interests,
  foundations,
}: Props) {
  return (
    <div className="mx-auto max-w-2xl px-5 py-10 space-y-10">
      <header>
        <h1 className="font-serif text-2xl text-foreground">Your profile</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Adjust the balance of what you see and tell us what would make your queue feel more right.
        </p>
      </header>

      <ModeBalanceSection initialValue={initialModeBalance} />

      <FeedbackSection initialFeedback={initialFeedback} />

      <InterestsSection interests={interests} />

      <FoundationsSection foundations={foundations} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode balance
// ---------------------------------------------------------------------------

function ModeBalanceSection({ initialValue }: { initialValue: number }) {
  const [value, setValue] = useState(initialValue);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const lastSaved = useRef(initialValue);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  function handleChange(v: number) {
    setValue(v);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => void save(v), 400);
  }

  async function save(v: number) {
    if (v === lastSaved.current) return;
    setStatus("saving");
    try {
      const res = await fetch("/api/survey/balance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode_balance: v }),
      });
      if (!res.ok) throw new Error("Save failed");
      lastSaved.current = v;
      setStatus("saved");
      setTimeout(() => setStatus((s) => (s === "saved" ? "idle" : s)), 1200);
    } catch {
      setStatus("error");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Problems or papers?</CardTitle>
      </CardHeader>
      <CardContent>
        <ModeBalanceControl value={value} onChange={handleChange} />
        <p className="mt-3 h-4 text-xs text-muted-foreground">
          {status === "saving" && "Saving…"}
          {status === "saved" && "Saved."}
          {status === "error" && "Couldn't save — try again."}
        </p>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Feedback toggles
// ---------------------------------------------------------------------------

function FeedbackSection({ initialFeedback }: { initialFeedback: Record<string, boolean> }) {
  const [active, setActive] = useState<Record<string, boolean>>(initialFeedback);
  const [error, setError] = useState<string | null>(null);

  async function toggle(key: string) {
    const next = !active[key];
    setActive((prev) => ({ ...prev, [key]: next }));
    setError(null);
    try {
      const res = await fetch("/api/profile/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, active: next }),
      });
      if (!res.ok) throw new Error("Save failed");
    } catch {
      setActive((prev) => ({ ...prev, [key]: !next }));
      setError("Couldn't save that — try again.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tell us what would help</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
          Toggle any that apply. These nudge the kind of content we generate for you — no exact
          dials, just a tilt.
        </p>
        <div className="flex flex-wrap gap-2">
          {FEEDBACK_PROMPTS.map(({ key, label }) => {
            const on = !!active[key];
            return (
              <button
                key={key}
                type="button"
                onClick={() => toggle(key)}
                aria-pressed={on}
                className={
                  "rounded-md border px-3 py-1.5 text-sm transition-colors duration-[var(--duration-fast)] " +
                  (on
                    ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                    : "border-border bg-background text-muted-foreground hover:bg-muted")
                }
              >
                {label}
              </button>
            );
          })}
        </div>
        {error && <p className="mt-3 text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Interest list
// ---------------------------------------------------------------------------

function InterestsSection({ interests }: { interests: ProfileInterest[] }) {
  const router = useRouter();
  const [editing, setEditing] = useState<ProfileInterest | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<string | null>(null);

  function toggleExpanded(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleRefreshSummaries() {
    setRefreshing(true);
    setRefreshStatus(null);
    try {
      const res = await fetch("/api/profile/regenerate-summaries", {
        method: "POST",
      });
      const data = (await res.json()) as { rewritten?: number; error?: string };
      if (!res.ok) throw new Error(data.error ?? "Refresh failed");
      setRefreshStatus(
        data.rewritten ? `Rewrote ${data.rewritten} summary${data.rewritten === 1 ? "" : "s"}.` : "Nothing to rewrite.",
      );
      router.refresh();
    } catch (err) {
      setRefreshStatus(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleDelete(interest: ProfileInterest) {
    if (!confirm(`Remove "${interest.node_title}" from your interests?`)) return;
    setBusy(interest.node_id);
    setError(null);
    try {
      const res = await fetch(`/api/interest/${interest.node_id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Your interests</CardTitle>
      </CardHeader>
      <CardContent>
        {interests.length > 0 && (
          <div className="mb-4 flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <span>
              {refreshStatus ?? "If the summaries below read like tag soup, rewrite them as prose."}
            </span>
            <button
              type="button"
              onClick={handleRefreshSummaries}
              disabled={refreshing}
              className="shrink-0 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-foreground transition-colors duration-[var(--duration-fast)] hover:bg-muted disabled:opacity-50"
            >
              {refreshing ? "Rewriting…" : "Rewrite summaries"}
            </button>
          </div>
        )}
        {interests.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No interests yet — add one from the daily tab or skill tree.
          </p>
        ) : (
          <ul className="space-y-3">
            {interests.map((interest) => {
              const isOpen = expanded.has(interest.user_interest_id);
              const queuedCount = interest.queued.length;
              return (
                <li
                  key={interest.user_interest_id}
                  className="border-b border-border pb-3 last:border-b-0 last:pb-0"
                >
                  <div className="flex items-start justify-between gap-4">
                    <button
                      type="button"
                      onClick={() => toggleExpanded(interest.user_interest_id)}
                      className="group min-w-0 flex-1 text-left"
                      aria-expanded={isOpen}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={
                            "text-muted-foreground transition-transform duration-[var(--duration-fast)] " +
                            (isOpen ? "rotate-90" : "")
                          }
                          aria-hidden
                        >
                          ›
                        </span>
                        <span className="font-serif text-base text-foreground group-hover:text-primary transition-colors duration-[var(--duration-fast)]">
                          {interest.node_title}
                        </span>
                        {queuedCount > 0 && (
                          <Badge variant="ghost" className="text-[10px]">
                            {queuedCount} queued
                          </Badge>
                        )}
                      </div>
                      {interest.intent_context && (
                        <p className="mt-1 ml-5 text-sm leading-relaxed text-muted-foreground">
                          {interest.intent_context}
                        </p>
                      )}
                    </button>
                    <div className="flex shrink-0 gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setEditing(interest)}
                      >
                        Edit
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(interest)}
                        disabled={busy === interest.node_id}
                      >
                        {busy === interest.node_id ? "…" : "Remove"}
                      </Button>
                    </div>
                  </div>

                  {isOpen && (
                    <InterestDetail interest={interest} />
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {error && <p className="mt-3 text-xs text-destructive">{error}</p>}
      </CardContent>

      {editing && (
        <DialogModal
          open={true}
          onOpenChange={(o) => !o && setEditing(null)}
          mode="preNode"
          preNode={{
            slug: editing.node_slug,
            title: editing.node_title,
            defaultIntentContext: editing.intent_context,
            mirrorOverride: `Editing ${editing.node_title}.`,
            followupPromptOverride: "What's off, or what would you change?",
          }}
          addedVia="explicit_request"
          title={`Edit ${editing.node_title}`}
          onComplete={() => {
            setEditing(null);
            router.refresh();
          }}
        />
      )}
    </Card>
  );
}

function InterestDetail({ interest }: { interest: ProfileInterest }) {
  return (
    <div className="mt-3 ml-5 space-y-3 border-l border-border pl-4">
      <div className="flex items-baseline gap-3 text-xs text-muted-foreground">
        <span>
          {interest.engagement_count} past engagement
          {interest.engagement_count === 1 ? "" : "s"}
        </span>
        <Link
          href={`/skill-tree`}
          className="text-foreground/70 underline-offset-2 hover:text-primary hover:underline"
        >
          See in skill tree →
        </Link>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          In your queue
        </p>
        {interest.queued.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing queued right now. The curator will surface something on the next plan.
          </p>
        ) : (
          <ul className="space-y-2">
            {interest.queued.map((item) => (
              <li
                key={item.queue_item_id}
                className="flex items-start justify-between gap-3"
              >
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/problem/${item.queue_item_id}`}
                    className="font-serif text-sm text-foreground hover:text-primary transition-colors duration-[var(--duration-fast)]"
                  >
                    {item.title}
                  </Link>
                  {item.added_reason && (
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {item.added_reason}
                    </p>
                  )}
                </div>
                <Badge variant="ghost" className="shrink-0 text-[10px] capitalize">
                  {item.state.replace("_", " ")}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Foundation state list
// ---------------------------------------------------------------------------

function FoundationsSection({ foundations }: { foundations: ProfileFoundation[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Foundations</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
          How the system reads your relationship with each foundation. These shift as you engage
          with content; you can&apos;t edit them directly here.
        </p>
        <ul className="space-y-2">
          {foundations.map((f) => (
            <li
              key={f.node_id}
              className="flex items-center justify-between gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0"
            >
              <span className="font-serif text-sm text-foreground">{f.node_title}</span>
              <Badge
                variant="outline"
                className={"border " + stateBadgeClass(f.state)}
              >
                {STATE_LABELS[f.state]}
              </Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
