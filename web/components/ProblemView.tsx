"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import MarkdownLatex from "@/lib/markdown";
import type { Problem, ProblemHint, Attempt } from "@/lib/types";

interface UploadedFile {
  name: string;
  previewUrl: string;
  storagePath: string;
}

interface Props {
  queueItemId: string;
  problem: Problem;
  hints: ProblemHint[];
  existingAttempt: Attempt | null;
}

type Step = 1 | 2 | 3 | 4;

function computeInitialStep(attempt: Attempt | null): Step {
  if (!attempt) return 1;
  if (attempt.parsed_markdown) return 3;
  if ((attempt.raw_image_paths as string[])?.length > 0) return 2;
  return 1;
}

export default function ProblemView({ queueItemId, problem, hints, existingAttempt }: Props) {
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
          hints={hints}
          openHints={openHints}
          onHintClick={handleHintClick}
          onStartWorking={handleStartWorking}
          onSkip={handleSkip}
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
  hints,
  openHints,
  onHintClick,
  onStartWorking,
  onSkip,
  loading,
}: {
  problem: Problem;
  hints: ProblemHint[];
  openHints: Set<number>;
  onHintClick: (level: number) => void;
  onStartWorking: () => void;
  onSkip: () => void;
  loading: boolean;
}) {
  return (
    <div className="space-y-10">
      {/* Problem statement */}
      <div
        className="font-serif text-base leading-[1.7] text-foreground
          [&_p]:mb-4 [&_p:last-child]:mb-0
          [&_strong]:font-semibold [&_em]:italic
          [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-2
          [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-2"
      >
        <MarkdownLatex source={problem.statement_md} />
      </div>

      {/* Context */}
      {problem.context_md && (
        <details className="group rounded-md border border-border">
          <summary className="cursor-pointer list-none px-5 py-3.5 text-sm font-medium text-foreground hover:bg-accent transition-colors duration-[var(--duration-fast)] [&::-webkit-details-marker]:hidden">
            <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Context</span>
          </summary>
          <div className="border-t border-border px-5 pb-5 pt-4">
            <div className="border-l-2 border-amber pl-4 font-serif text-sm leading-[1.7] text-muted-foreground
              [&_p]:mb-3 [&_p:last-child]:mb-0 [&_strong]:font-semibold [&_em]:italic">
              <MarkdownLatex source={problem.context_md} />
            </div>
          </div>
        </details>
      )}

      {/* Hints */}
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
                  className="flex w-full items-center justify-between px-4 py-3 text-left text-sm hover:bg-accent transition-colors duration-[var(--duration-fast)]"
                >
                  <span className="font-medium text-foreground">
                    <span className="text-muted-foreground mr-1.5">Hint {hint.level}.</span>
                    {openHints.has(hint.level) ? "Hide" : "Show"}
                  </span>
                  <span className="text-xs text-muted-foreground">{openHints.has(hint.level) ? "▲" : "▼"}</span>
                </button>
                {openHints.has(hint.level) && (
                  <div className="border-t border-border px-4 pb-4 pt-3">
                    <div className={`font-serif text-sm leading-relaxed text-muted-foreground
                      [&_p]:mb-2 [&_p:last-child]:mb-0 [&_.katex-display]:my-3`}>
                      <MarkdownLatex source={hint.text} />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onSkip}
          disabled={loading}
          className="rounded-md border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors duration-[var(--duration-fast)] disabled:opacity-50"
        >
          Skip — I&apos;ve got this
        </button>
        <button
          type="button"
          onClick={onStartWorking}
          disabled={loading}
          className="flex-1 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/85 transition-colors duration-[var(--duration-fast)] disabled:opacity-50"
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
      <h2 className="mb-4 text-base font-semibold text-foreground">Upload your solution</h2>

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
          <div className={`min-h-[200px] rounded-md border border-border bg-card px-4 py-3
            font-serif text-sm leading-[1.7] text-foreground
            [&_p]:mb-3 [&_p:last-child]:mb-0
            [&_strong]:font-semibold [&_em]:italic
            [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-1
            [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-1
            [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded`}>
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

function Step4Feedback({ gradeMd, onDone }: { gradeMd: string; onDone: () => void }) {
  return (
    <div>
      <h2 className="mb-4 text-base font-semibold text-foreground">Feedback</h2>
      <div className={`mb-8 rounded-md border border-border bg-card px-5 py-5
        font-serif text-sm leading-[1.7] text-foreground
        [&_p]:mb-4 [&_p:last-child]:mb-0
        [&_strong]:font-semibold [&_em]:italic
        [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-1.5
        [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-1.5
        [&_code]:font-mono [&_code]:text-xs [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
        [&_blockquote]:border-l-2 [&_blockquote]:border-amber [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground`}>
        <MarkdownLatex source={gradeMd} />
      </div>
      <Button type="button" onClick={onDone} className="w-full">
        Done → Back to daily
      </Button>
    </div>
  );
}
