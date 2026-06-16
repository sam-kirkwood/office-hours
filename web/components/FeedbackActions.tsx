"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function FeedbackResolveButton({ id }: { id: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function resolve() {
    setLoading(true);
    try {
      await fetch(`/api/admin/feedback/${id}/resolve`, { method: "POST" });
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={resolve} disabled={loading}>
      {loading ? "Resolving…" : "Mark resolved"}
    </Button>
  );
}
