"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDown } from "lucide-react";
import { toast } from "sonner";
import MarkdownLatex from "@/lib/markdown";
import type { Problem, ProblemHint, Attempt } from "@/lib/types";
import type { SiblingKind } from "@/lib/pythonApi";

interface UploadedFile {
  name: string;
  previewUrl: string;
  storagePath: string;
}

interface Props {
  queueItemId: string;
  problem: Problem;
  topicTitle: string | null;
  hints: ProblemHint[];
  existingAttempt: Attempt | null;
  parentQueueItemId: string | null;
}

type Step = 1 | 2 | 3 | 4;

// Shared reading-surface styling for problem prose. Beyond the basic
// paragraph/list rules, this styles the structural markdown the generator now
// emits — `## Setup` / `## The problem` section headings, `---` rules, GFM
// tables (e.g. a phase diagram), blockquotes — and gives display equations
// vertical breathing room (d8) plus horizontal scroll so a wide equation or
// table can't overflow the page on mobile.
// Note: deliberately sets no font-size — each call site picks `text-base`
// (statement) or `text-sm` (context, hints, feedback). Two same-specificity
// size utilities in one class string don't override reliably by order.
const READING_PROSE =
  "font-serif leading-[1.7] text-foreground " +
  "[&_p]:mb-4 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_em]:italic " +
  "[&_h2]:mt-8 [&_h2]:mb-3 [&_h2]:text-xs [&_h2]:font-semibold [&_h2]:uppercase [&_h2]:tracking-widest [&_h2]:text-muted-foreground [&_h2:first-child]:mt-0 " +
  "[&_h3]:mt-6 [&_h3]:mb-2 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-foreground " +
  "[&_hr]:my-6 [&_hr]:border-border " +
  "[&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-2 " +
  "[&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-2 " +
  "[&_code]:font-mono [&_code]:text-[0.85em] [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded " +
  "[&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:border-amber [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground " +
  "[&_table]:my-5 [&_table]:w-full [&_table]:border-collapse [&_table]:text-sm " +
  "[&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-3 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold " +
  "[&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-1.5 " +
  "[&_.katex-display]:my-5 [&_.katex-display]:overflow-x-auto [&_.katex-display]:overflow-y-hidden [&_.katex-display]:py-1";

function computeInitialStep(attempt: Attempt | null): Step {
  if (!attempt) return 1;
  if (attempt.parsed_markdown) return 3;
  if ((attempt.raw_image_paths as string[])?.length > 0) return 2;
  return 1;
}

export default function ProblemView({ queueItemId, problem, topicTitle, hints, existingAttempt, parentQueueItemId }: Props) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>(computeInitialStep(existingAttempt));
  const [attemptId, setAttemptId] = useState<string | null>(existingAttempt?.id ?? null);
  const [openHints, setOpenHints] = useState<Set<number>>(
    new Set((existingAttempt?.hint_levels_used as number[]) ?? []),
  );
  const [uploads, setUploads] = useState<UploadedFile[]>([]);
  const [parsedMd, setParsedMd] = useState(existingAttempt?.parsed_markdown ?? "");
  const [editedMd, setEditedMd] = useState(existingAttempt?.parsed_markdown ?? "");
  const [gradeMd, setGradeMd] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState<SiblingKind | null>(null);
  const [siblingMsg, setSiblingMsg] = useState<string | null>(null);
  const [revertingToParent, setRevertingToParent] = useState(false);

  async function handleHintClick(level: number) {
    const isOpen = openHints.has(level);
    const next = new Set(openHints);
    if (isOpen) {
      next.delete(level);
      setOpenHints(next);
      return;
    }
    next.add(level);
    setOpenHints(next);
    if (attemptId) {
      fetch(`/api/problem/${queueItemId}/hint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attempt_id: attemptId, level }),
      }).catch(() => {});
    }
  }

  async function handleSkip() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/skip`, { method: "POST" });
      if (res.ok) router.push("/daily");
      else setError("Skip failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDefer() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/defer`, { method: "POST" });
      if (res.ok) router.push("/daily");
      else {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setError(body.error ?? "Couldn't defer this problem");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRequestSibling(kind: SiblingKind) {
    setRequesting(kind);
    setSiblingMsg(null);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/sibling`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kind }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Request failed");
      if (data.is_max_difficulty) {
        setSiblingMsg("This is already at the highest difficulty.");
        return;
      }
      if (data.is_min_difficulty) {
        setSiblingMsg("This is already at the lowest difficulty.");
        return;
      }
      if (data.sibling_queue_item_id) {
        router.push(`/problem/${data.sibling_queue_item_id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't get a different version — try again.");
    } finally {
      setRequesting(null);
    }
  }

  async function handleRevertSibling() {
    setRevertingToParent(true);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/revert-sibling`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Revert failed");
      router.push(`/problem/${data.parent_queue_item_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't revert — try again.");
      setRevertingToParent(false);
    }
  }

  async function handleStartWorking() {
    if (attemptId) { setStep(2); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hint_levels_used: [...openHints] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to start");
      setAttemptId(data.attempt_id);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleFiles(files: FileList) {
    setError(null);
    setUploading(true);
    for (const file of Array.from(files)) {
      try {
        const signRes = await fetch("/api/upload/sign", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: file.name, contentType: file.type }),
        });
        if (!signRes.ok) throw new Error("Failed to get upload URL");
        const { signedUrl, path } = await signRes.json();

        const uploadRes = await fetch(signedUrl, {
          method: "PUT",
          headers: { "Content-Type": file.type },
          body: file,
        });
        if (!uploadRes.ok) throw new Error("Upload to storage failed");

        setUploads((prev) => [
          ...prev,
          { name: file.name, previewUrl: URL.createObjectURL(file), storagePath: path },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        break;
      }
    }
    setUploading(false);
  }

  async function handleParse() {
    if (!attemptId || uploads.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attempt_id: attemptId,
          image_paths: uploads.map((u) => u.storagePath),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Parse failed");
      setParsedMd(data.parsed_markdown);
      setEditedMd(data.parsed_markdown);
      setStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parse failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!attemptId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/problem/${queueItemId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attempt_id: attemptId, user_edited_markdown: editedMd }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Submit failed");
      setGradeMd(data.grade_response_md);
      setStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-5 py-12">
      <div className="mb-8">
        <Link href="/daily" className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]">
          ← Back
        </Link>
      </div>

      {error && <p className="mb-6 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}

      {step === 1 && (
        <Step1View
          problem={problem}
          topicTitle={topicTitle}
          hints={hints}
          openHints={openHints}
          onHintClick={handleHintClick}
          onStartWorking={handleStartWorking}
          onSkip={handleSkip}
          onDefer={handleDefer}
          onRequestSibling={handleRequestSibling}
          onRevertSibling={handleRevertSibling}
          requesting={requesting}
          revertingToParent={revertingToParent}
          siblingMsg={siblingMsg}
          parentQueueItemId={parentQueueItemId}
          loading={loading}
        />
      )}

      {step === 2 && (
        <Step2Upload
          uploads={uploads}
          uploading={uploading}
          loading={loading}
          fileInputRef={fileInputRef}
          onFiles={handleFiles}
          onParse={handleParse}
          onBack={() => setStep(1)}
        />
      )}

      {step === 3 && (
        <Step3Review
          parsedMd={parsedMd}
          editedMd={editedMd}
          loading={loading}
          onEditedMdChange={setEditedMd}
          onSubmit={handleSubmit}
          onReupload={() => setStep(2)}
        />
      )}

      {step === 4 && (
        <Step4Feedback
          gradeMd={gradeMd ?? ""}
          queueItemId={queueItemId}
          attemptId={attemptId}
          onDone={() => router.push("/daily")}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step sub-views
// ---------------------------------------------------------------------------

function Step1View({
  problem,
  topicTitle,
  hints,
  openHints,
  onHintClick,
  onStartWorking,
  onSkip,
  onDefer,
  onRequestSibling,
  onRevertSibling,
  requesting,
  revertingToParent,
  siblingMsg,
  parentQueueItemId,
  loading,
}: {
  problem: Problem;
  topicTitle: string | null;
  hints: ProblemHint[];
  openHints: Set<number>;
  onHintClick: (level: number) => void;
  onStartWorking: () => void;
  onSkip: () => void;
  onDefer: () => void;
  onRequestSibling: (kind: SiblingKind) => void;
  onRevertSibling: () => void;
  requesting: SiblingKind | null;
  revertingToParent: boolean;
  siblingMsg: string | null;
  parentQueueItemId: string | null;
  loading: boolean;
}) {
  return (
    <div className="space-y-8">
      {/* Header — topic metadata line (d11) + title (d6) */}
      <header className="space-y-1.5">
        {topicTitle && (
          <p className="text-xs font-semibold uppercase tracking-widest text-amber">
            {topicTitle}
          </p>
        )}
        {problem.title && (
          <h1 className="font-serif text-2xl font-semibold leading-snug text-foreground">
            {problem.title}
          </h1>
        )}
      </header>

      {/* Context — first, above the statement (d7), always open. Kept in the
          problem-mode amber family, presented as supporting reading. */}
      {problem.context_md && (
        <div className="rounded-md border border-border bg-muted/40 px-5 py-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Context
          </p>
          <div className={`border-l-2 border-amber pl-4 text-sm ${READING_PROSE}`}>
            <MarkdownLatex source={problem.context_md} />
          </div>
        </div>
      )}

      {/* Problem statement */}
      <div className={`text-base ${READING_PROSE}`}>
        <MarkdownLatex source={problem.statement_md} />
      </div>

      {/* Hints — each labelled with the part it addresses (d10) */}
      {hints.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Hints
          </p>
          <div className="space-y-1.5">
            {hints.map((hint) => (
              <div key={hint.level} className="rounded-md border border-border overflow-hidden">
                <button
                  type="button"
                  onClick={() => onHintClick(hint.level)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm hover:bg-accent transition-colors duration-[var(--duration-fast)]"
                >
                  <span className="flex items-center gap-2 min-w-0">
                    {hint.part_label && (
                      <span className="shrink-0 rounded-sm bg-muted px-1.5 py-0.5 text-[0.7rem] font-medium text-muted-foreground">
                        {hint.part_label}
                      </span>
                    )}
                    <span className="font-medium text-foreground">
                      <span className="text-muted-foreground mr-1.5">Hint {hint.level}.</span>
                      {openHints.has(hint.level) ? "Hide" : "Show"}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">{openHints.has(hint.level) ? "▲" : "▼"}</span>
                </button>
                {openHints.has(hint.level) && (
                  <div className="border-t border-border px-4 pb-4 pt-3">
                    <div className={`text-sm text-muted-foreground ${READING_PROSE}`}>
                      <MarkdownLatex source={hint.text} />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Correction controls — "This version" dropdown (§A3) */}
      <div className="space-y-2">
        {parentQueueItemId && (
          <p className="text-sm text-muted-foreground">
            <button
              type="button"
              onClick={onRevertSibling}
              disabled={revertingToParent || loading}
              className="hover:text-foreground transition-colors duration-[var(--duration-fast)] disabled:opacity-50"
            >
              {revertingToParent ? "Reverting…" : "← Too hard? Back to the previous version"}
            </button>
          </p>
        )}
        <div className="flex items-center gap-3">
          {requesting ? (
            <p className="text-sm text-muted-foreground">
              {requesting === "harder"
                ? "Making a tougher one…"
                : requesting === "easier"
                  ? "Finding an easier one…"
                  : "Making one that explains more…"}
            </p>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={loading}>
                  This version <ChevronDown className="ml-1 size-3" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-52">
                <DropdownMenuLabel>Request a different version</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => onRequestSibling("easier")}>
                  Easier
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onRequestSibling("harder")}>
                  Harder
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onRequestSibling("assume_less")}>
                  Explain more / Assume less
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          {siblingMsg && (
            <p className="text-sm text-muted-foreground">{siblingMsg}</p>
          )}
        </div>
      </div>

      {/* Actions — stack on phone (Start working primary at the bottom),
          row on sm+ where the three buttons fit comfortably. */}
      <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:flex-wrap">
        <button
          type="button"
          onClick={onSkip}
          disabled={loading}
          className="rounded-md border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors duration-[var(--duration-fast)] disabled:opacity-50"
        >
          I already know this
        </button>
        <button
          type="button"
          onClick={onDefer}
          disabled={loading}
          className="rounded-md border border-[var(--forest)]/50 px-4 py-2.5 text-sm font-medium text-[var(--forest)] hover:bg-[var(--forest-subtle)] transition-colors duration-[var(--duration-fast)] disabled:opacity-50"
        >
          Not ready yet — come back later
        </button>
        <button
          type="button"
          onClick={onStartWorking}
          disabled={loading}
          className="rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/85 transition-colors duration-[var(--duration-fast)] disabled:opacity-50 sm:flex-1"
        >
          {loading ? "Starting…" : "Start working"}
        </button>
      </div>
    </div>
  );
}

function Step2Upload({
  uploads,
  uploading,
  loading,
  fileInputRef,
  onFiles,
  onParse,
  onBack,
}: {
  uploads: UploadedFile[];
  uploading: boolean;
  loading: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onFiles: (files: FileList) => void;
  onParse: () => void;
  onBack: () => void;
}) {
  return (
    <div>
      <h2 className="mb-2 text-base font-semibold text-foreground">Upload your solution</h2>

      {/* d13 — how to lay out the page so the parser reads it cleanly */}
      <div className="mb-4 rounded-md border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
        <span className="font-medium text-foreground">For the cleanest read:</span> label each
        part <span className="font-mono text-xs">(a)</span>, <span className="font-mono text-xs">(b)</span>,
        … as you go, keep one part per page where you can, and add a page number if you photograph
        more than one sheet. Neat is plenty — it doesn&apos;t need to be tidy.
      </div>

      <button
        type="button"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files); }}
        disabled={uploading || loading}
        className="mb-4 flex w-full flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-border bg-muted px-4 py-10 text-sm text-muted-foreground transition-colors duration-[var(--duration-fast)] hover:border-foreground/25 hover:bg-accent/40 disabled:opacity-50"
      >
        <span className="text-3xl">📷</span>
        <span className="font-medium text-foreground">
          {uploading ? "Uploading…" : "Tap to take a photo or choose files"}
        </span>
        <span className="text-xs">JPG, PNG, HEIC — multiple allowed</span>
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="hidden"
        onChange={(e) => { if (e.target.files?.length) onFiles(e.target.files); }}
      />

      {uploads.length > 0 && (
        <div className="mb-6 flex flex-col gap-3">
          {uploads.map((u, i) => (
            <div key={i} className="flex items-center gap-3 rounded-md border border-border bg-card p-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={u.previewUrl} alt={`Preview ${i + 1}`} className="h-16 w-16 rounded object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{u.name}</p>
                <p className="text-xs text-[var(--forest)]">Uploaded ✓</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-3">
        <Button type="button" variant="outline" onClick={onBack}>
          ← Back
        </Button>
        {uploads.length > 0 && (
          <Button
            type="button"
            onClick={onParse}
            disabled={loading || uploading}
            className="flex-1"
          >
            {loading ? "Parsing…" : "Parse my solution"}
          </Button>
        )}
      </div>
    </div>
  );
}

function Step3Review({
  parsedMd,
  editedMd,
  loading,
  onEditedMdChange,
  onSubmit,
  onReupload,
}: {
  parsedMd: string;
  editedMd: string;
  loading: boolean;
  onEditedMdChange: (v: string) => void;
  onSubmit: () => void;
  onReupload: () => void;
}) {
  return (
    <div>
      <h2 className="mb-1 text-base font-semibold text-foreground">Review your solution</h2>
      <p className="mb-4 text-sm text-muted-foreground">
        Edit any transcription errors, then submit for feedback.
      </p>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Edit
          </p>
          <textarea
            value={editedMd}
            onChange={(e) => onEditedMdChange(e.target.value)}
            rows={16}
            className="w-full rounded-md border border-border bg-muted px-3 py-2 font-mono text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Preview
          </p>
          <div className={`min-h-[200px] rounded-md border border-border bg-card px-4 py-3 text-sm ${READING_PROSE}`}>
            <MarkdownLatex source={editedMd} />
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <Button type="button" variant="outline" onClick={onReupload}>
          Re-upload
        </Button>
        <Button
          type="button"
          onClick={onSubmit}
          disabled={loading || !editedMd.trim()}
          className="flex-1"
        >
          {loading ? "Getting feedback…" : "Submit for feedback"}
        </Button>
      </div>
    </div>
  );
}

function Step4Feedback({
  gradeMd,
  queueItemId,
  attemptId,
  onDone,
}: {
  gradeMd: string;
  queueItemId: string;
  attemptId: string | null;
  onDone: () => void;
}) {
  const [fit, setFit] = useState<"easier" | "harder" | "assume_less" | null>(null);

  async function handleFit(kind: "easier" | "harder" | "assume_less") {
    if (!attemptId || fit !== null) return;
    setFit(kind);
    toast.success("Thanks — we'll factor that in.", { duration: 3000 });
    fetch(`/api/problem/${queueItemId}/fit-feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attempt_id: attemptId, kind }),
    }).catch(() => {});
  }

  const fitLabels: Array<{ kind: "easier" | "harder" | "assume_less"; label: string }> = [
    { kind: "easier", label: "Too easy" },
    { kind: "harder", label: "Too hard" },
    { kind: "assume_less", label: "Assumed too much" },
  ];

  return (
    <div>
      <h2 className="mb-4 text-base font-semibold text-foreground">Feedback</h2>
      <div className={`mb-8 rounded-md border border-border bg-card px-5 py-5 text-sm ${READING_PROSE}`}>
        <MarkdownLatex source={gradeMd} />
      </div>

      {attemptId && (
        <div className="mb-6">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            How did this feel?
          </p>
          <div className="flex flex-wrap gap-2">
            {fitLabels.map(({ kind, label }) => (
              <button
                key={kind}
                type="button"
                onClick={() => handleFit(kind)}
                disabled={fit !== null}
                className={
                  "rounded-md border px-3 py-1.5 text-sm transition-colors duration-[var(--duration-fast)] disabled:cursor-default " +
                  (fit === kind
                    ? "border-primary bg-[var(--amber-subtle)] text-foreground"
                    : "border-border bg-background text-muted-foreground hover:bg-muted disabled:opacity-60")
                }
              >
                {fit === kind ? "Noted" : label}
              </button>
            ))}
            <button
              type="button"
              onClick={onDone}
              disabled={fit !== null}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted transition-colors duration-[var(--duration-fast)] disabled:opacity-40"
            >
              About right
            </button>
          </div>
        </div>
      )}

      <Button type="button" onClick={onDone} className="w-full">
        Done → Back to daily
      </Button>
    </div>
  );
}
