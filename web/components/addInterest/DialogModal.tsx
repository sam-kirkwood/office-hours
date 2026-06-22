"use client";

// Modal wrapper around Dialog, used by post-onboarding entry points:
//   - Skill-tree NodePanel "Add to my interests"
//   - Stage 7 SurveyNodePanel "Edit"
//   - Daily-tab RequestBox "Add it" branch
//
// The orchestration here is single-segment-only. Callers either pass a
// pre-known node (preNode path — Edit / Add to my interests) or a raw_text
// to /parse first (RequestBox).

import { useEffect, useState } from "react";
import {
  Dialog as ShadDialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import Dialog from "./Dialog";
import NodeReadiness from "./NodeReadiness";
import type {
  AddedVia,
  DialogResolved,
  PreNodeInput,
} from "./types";
import type {
  ParsedInterestSegmentDTO,
  NodeReadinessState,
} from "@/lib/pythonApi";

interface PreNodeProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "preNode";
  preNode: PreNodeInput;
  addedVia: AddedVia;
  title?: string;
  onComplete?: (result: DialogResolved) => void;
}

interface SegmentProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "segment";
  rawText: string;
  segment: ParsedInterestSegmentDTO;
  addedVia: AddedVia;
  title?: string;
  onComplete?: (result: DialogResolved) => void;
}

type Props = PreNodeProps | SegmentProps;

type Phase = "dialog" | "tour" | "done";

export default function DialogModal(props: Props) {
  const { open, onOpenChange, addedVia, onComplete } = props;
  const [phase, setPhase] = useState<Phase>("dialog");
  const [resolved, setResolved] = useState<DialogResolved | null>(null);

  useEffect(() => {
    if (open) {
      setPhase("dialog");
      setResolved(null);
    }
  }, [open]);

  function handleResolved(r: DialogResolved) {
    setResolved(r);
    setPhase(r.node_readiness.length > 0 ? "tour" : "done");
    if (r.node_readiness.length === 0) {
      onComplete?.(r);
      onOpenChange(false);
    }
  }

  async function handleReadinessSubmit(args: {
    nodeStates: Array<{ nodeId: string; state: NodeReadinessState }>;
  }) {
    if (resolved && args.nodeStates.length > 0) {
      try {
        await fetch("/api/add-interest/node-readiness", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_interest_id: resolved.user_interest_id,
            node_states: args.nodeStates.map((s) => ({
              node_id: s.nodeId,
              state: s.state,
            })),
          }),
        });
      } catch (err) {
        console.error("node-readiness write failed:", err);
      }
    }
    if (resolved) onComplete?.(resolved);
    onOpenChange(false);
  }

  const titleText =
    props.title ?? (props.mode === "preNode" ? props.preNode.title : "Add interest");

  const dialogInput =
    props.mode === "preNode"
      ? { source: "preNode" as const, preNode: props.preNode }
      : { source: "segment" as const, segment: props.segment };

  const rawText =
    props.mode === "preNode" ? props.preNode.title : props.rawText;

  return (
    <ShadDialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-serif text-base">{titleText}</DialogTitle>
        </DialogHeader>

        {phase === "dialog" && (
          <Dialog
            rawText={rawText}
            input={dialogInput}
            addedVia={addedVia}
            presentation="modal"
            onResolved={handleResolved}
            onCancel={() => onOpenChange(false)}
          />
        )}

        {phase === "tour" && resolved && (
          <div className="-mx-4 -mb-4 max-h-[70vh] overflow-y-auto rounded-b-xl border-t bg-background">
            <NodeReadiness
              interestTitle={rawText}
              tiles={resolved.node_readiness}
              seenNodeIds={new Set()}
              showSkipRemaining={false}
              onSubmit={handleReadinessSubmit}
            />
          </div>
        )}
      </DialogContent>
    </ShadDialog>
  );
}
