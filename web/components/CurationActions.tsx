"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function RunReportButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const router = useRouter();

  async function handleRun() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch("/api/admin/curation/run", { method: "POST" });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Unknown error");
      setMessage(`Created ${json.proposals_created} proposal(s).`);
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button variant="secondary" onClick={handleRun} disabled={loading}>
        {loading ? "Running…" : "Run curation report"}
      </Button>
      {message && <span className="text-sm text-muted-foreground">{message}</span>}
    </div>
  );
}

export function DecideButton({
  proposalId,
  action,
}: {
  proposalId: string;
  action: "approve" | "reject";
}) {
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleClick() {
    setLoading(true);
    try {
      await fetch(`/api/admin/proposals/${proposalId}/decide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      variant={action === "approve" ? "default" : "outline"}
      size="sm"
      onClick={handleClick}
      disabled={loading}
    >
      {action === "approve" ? "Approve" : "Reject"}
    </Button>
  );
}

export function ApplyButton({ count }: { count: number }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const router = useRouter();

  async function handleApply() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch("/api/admin/proposals/apply", { method: "POST" });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Unknown error");
      setMessage(`Applied ${json.applied_count} proposals. Megagraph snapshot taken.`);
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <Button variant="default" onClick={handleApply} disabled={loading || count === 0}>
        {loading ? "Applying…" : `Apply ${count} approved proposal${count === 1 ? "" : "s"}`}
      </Button>
      {message && <span className="text-sm text-muted-foreground">{message}</span>}
    </div>
  );
}
