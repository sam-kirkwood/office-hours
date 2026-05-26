"use client";

import { useSelectedLayoutSegment } from "next/navigation";

// The progress chip shown at the top of every survey stage. Reads which
// child segment is active to compute "Step N of M".
//
// `confirm` is conceptually the last step but we count it as part of the
// 5 visible stages so the chip reads naturally to the user (Stages 4 and 5
// are stubbed this session — see TODO(2d) in /api/survey/interests/route.ts).

const ORDER = ["background", "foundations", "interests", "balance", "confirm"] as const;
type Segment = (typeof ORDER)[number];

const LABELS: Record<Segment, string> = {
  background: "Background",
  foundations: "Foundations",
  interests: "Interests",
  balance: "Balance",
  confirm: "Confirm",
};

export default function SurveyProgress() {
  const segment = useSelectedLayoutSegment();
  const idx = ORDER.indexOf(segment as Segment);
  if (idx < 0) return null;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-semibold uppercase tracking-widest text-[var(--forest)]">
        Step {idx + 1} of {ORDER.length}
      </span>
      <span className="text-xs uppercase tracking-widest text-muted-foreground">
        {LABELS[ORDER[idx]]}
      </span>
    </div>
  );
}
