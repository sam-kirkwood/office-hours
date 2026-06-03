"use client";

import { toast } from "sonner";
import type { useRouter } from "next/navigation";

// Fire-and-forget queue request (phase-10-rev-plan §Step 4 #39).
// Shows a loading toast immediately, upgrades to a success toast with a
// "Go to it now →" action when the API returns with a queue_item_id, or to
// a deferred message when the item isn't ready (e.g. paper-propose path).
// Calls router.refresh() on resolution so /daily picks up the new item
// without a manual reload.

type Router = ReturnType<typeof useRouter>;

interface Body {
  node_id?: string;
  raw_text?: string;
  kind_hint?: "problem" | "paper" | "refresher";
  skip_interest_add?: boolean;
  parent_queue_item_id?: string;
}

interface Labels {
  pending: string;        // shown while in flight, e.g. "Finding a problem on Calculus…"
  queued: string;         // shown when API returns with no queue_item_id
}

interface QueueRequestResponse {
  queue_item_id: string | null;
  kind?: string;
  message?: string;
  error?: string;
}

interface OptimisticQueueRequestArgs {
  body: Body;
  // Receives the resulting queue item's id and the response `kind`
  // (e.g. "problem", "paper_engagement", "refresher", "concept_review") so
  // callers whose kind_hint can resolve to multiple kinds (e.g. refresher
  // falling back to concept_review) can route correctly.
  targetPath: (queueItemId: string, kind: string | undefined) => string;
  router: Router;
  labels: Labels;
}

export function optimisticQueueRequest({
  body,
  targetPath,
  router,
  labels,
}: OptimisticQueueRequestArgs): Promise<QueueRequestResponse> {
  const toastId = toast.loading(labels.pending, { duration: Infinity });

  const promise = fetch("/api/queue/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
    .then(async (res) => {
      const data = (await res.json()) as QueueRequestResponse;
      if (!res.ok) {
        throw new Error(data.error ?? "Request failed");
      }
      return data;
    })
    .then((data) => {
      if (data.queue_item_id) {
        const id = data.queue_item_id;
        toast.success("Ready.", {
          id: toastId,
          action: {
            label: "Go to it now →",
            onClick: () => router.push(targetPath(id, data.kind)),
          },
          duration: 8000,
        });
      } else {
        toast.message(data.message ?? labels.queued, {
          id: toastId,
          duration: 5000,
        });
      }
      router.refresh();
      return data;
    })
    .catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : "Couldn't add that — try again.";
      toast.error(msg, { id: toastId, duration: 6000 });
      throw err;
    });

  return promise;
}
