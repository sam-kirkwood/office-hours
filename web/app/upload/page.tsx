"use client";

import { useState, useRef } from "react";
import Link from "next/link";

interface UploadedFile {
  name: string;
  previewUrl: string;
  storagePath: string;
}

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploads, setUploads] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function handleFiles(files: FileList) {
    setError(null);
    setUploading(true);

    for (const file of Array.from(files)) {
      try {
        // Get a signed upload URL from our API
        const res = await fetch("/api/upload/sign", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: file.name,
            contentType: file.type,
          }),
        });

        if (!res.ok) {
          const body = await res.json();
          throw new Error(body.error ?? "Failed to get upload URL");
        }

        const { signedUrl, path } = await res.json();

        // Upload directly to Supabase Storage
        const uploadRes = await fetch(signedUrl, {
          method: "PUT",
          headers: { "Content-Type": file.type },
          body: file,
        });

        if (!uploadRes.ok) {
          throw new Error("Upload to storage failed");
        }

        setUploads((prev) => [
          ...prev,
          {
            name: file.name,
            previewUrl: URL.createObjectURL(file),
            storagePath: path,
          },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        break;
      }
    }

    setUploading(false);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) {
      handleFiles(e.target.files);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    if (e.dataTransfer.files?.length) {
      handleFiles(e.dataTransfer.files);
    }
  }

  if (submitted) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="text-center">
          <p className="mb-2 text-2xl font-semibold text-zinc-900">
            Solution submitted!
          </p>
          <p className="mb-6 text-sm text-zinc-500">
            Grading is not yet wired up — this is Phase 1.
          </p>
          <Link
            href="/daily"
            className="text-sm font-medium text-zinc-700 underline underline-offset-2"
          >
            ← Back to today&apos;s problem
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-10">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/daily" className="text-sm text-zinc-500 hover:text-zinc-800">
          ← Problem
        </Link>
        <h1 className="text-xl font-semibold text-zinc-900">
          Upload your solution
        </h1>
      </div>

      {/* Drop zone / file picker */}
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        disabled={uploading}
        className="mb-4 flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-zinc-300 bg-zinc-50 px-4 py-10 text-sm text-zinc-500 transition hover:border-zinc-400 hover:bg-zinc-100 disabled:opacity-50"
      >
        <span className="text-3xl">📷</span>
        <span className="font-medium text-zinc-700">
          {uploading ? "Uploading…" : "Tap to take a photo or choose files"}
        </span>
        <span className="text-xs text-zinc-400">JPG, PNG, HEIC — multiple allowed</span>
      </button>

      {/* Hidden file input — capture="environment" opens rear camera on mobile */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="hidden"
        onChange={handleChange}
      />

      {error && (
        <p className="mb-4 text-sm text-red-600">{error}</p>
      )}

      {/* Previews */}
      {uploads.length > 0 && (
        <div className="mb-6 flex flex-col gap-3">
          {uploads.map((u, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg ring-1 ring-zinc-200 p-3"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={u.previewUrl}
                alt={`Preview ${i + 1}`}
                className="h-16 w-16 rounded object-cover"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-zinc-800">
                  {u.name}
                </p>
                <p className="text-xs text-green-600">Uploaded ✓</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        {uploads.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="flex-1 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
            >
              Add more
            </button>
            <button
              type="button"
              onClick={() => setSubmitted(true)}
              disabled={uploading}
              className="flex-1 rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-50"
            >
              Submit
            </button>
          </>
        )}
      </div>
    </div>
  );
}
