"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

const CATEGORIES = [
  { value: "bug", label: "Bug" },
  { value: "confusing_copy", label: "Confusing copy" },
  { value: "bad_problem_or_paper", label: "Bad problem or paper" },
  { value: "other", label: "Other" },
] as const;

interface FeedbackDialogProps {
  // When provided, the dialog is externally controlled (e.g. by RequestBox
  // for the feedback-redirect path). When omitted, internal state is used
  // (existing AdminNav usage — unchanged).
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  // Pre-fill the message textarea (e.g. with the user's raw curiosity-box text).
  initialBody?: string;
  // Custom trigger element. Defaults to the nav "Feedback" button.
  trigger?: React.ReactNode;
}

export function FeedbackDialog({
  open: externalOpen,
  onOpenChange: externalOnOpenChange,
  initialBody,
  trigger,
}: FeedbackDialogProps = {}) {
  const controlled = externalOpen !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlled ? externalOpen : internalOpen;

  function setOpen(value: boolean) {
    // Sync body from initialBody when the dialog opens so a redirect pre-fill
    // takes effect at open time (avoids a setState-in-effect lint error).
    if (value && initialBody !== undefined) {
      setBody(initialBody);
    }
    if (controlled) {
      externalOnOpenChange?.(value);
    } else {
      setInternalOpen(value);
    }
  }

  const [category, setCategory] = useState<string>("other");
  const [body, setBody] = useState(initialBody ?? "");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: window.location.href, category, body }),
      });
      if (!res.ok) {
        const { error } = (await res.json()) as { error: string };
        toast.error(error ?? "Something went wrong — try again.");
        return;
      }
      toast.success("Feedback sent — thank you.");
      setOpen(false);
      setBody("");
      setCategory("other");
    } finally {
      setSubmitting(false);
    }
  }

  const defaultTrigger = (
    <button className="text-xs text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]">
      Feedback
    </button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger ?? defaultTrigger}</DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Send feedback</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fb-category">Category</Label>
            <select
              id="fb-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {CATEGORIES.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fb-body">Message</Label>
            <Textarea
              id="fb-body"
              rows={3}
              placeholder="What happened or what's wrong?"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={submitting || !body.trim()} size="sm">
            {submitting ? "Sending…" : "Send feedback"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
