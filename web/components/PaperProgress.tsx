"use client";

interface Props {
  total: number;
  currentIdx: number;
  answeredIds: Set<string>;
  questionIds: string[];
}

export default function PaperProgress({
  total,
  currentIdx,
  answeredIds,
  questionIds,
}: Props) {
  if (total === 0) return null;

  const display = Math.min(currentIdx + 1, total);

  return (
    <div className="mb-6 flex items-center gap-3">
      <p className="text-sm font-medium text-foreground">
        Question {display} of {total}
      </p>
      <div className="flex items-center gap-1.5" aria-hidden>
        {questionIds.map((qid, idx) => {
          const answered = answeredIds.has(qid);
          const isCurrent = idx === currentIdx;
          const cls = answered
            ? "bg-[var(--forest)] border-[var(--forest)]"
            : isCurrent
              ? "border-[var(--primary)] bg-[var(--amber-subtle)] ring-2 ring-[var(--primary)]/30"
              : "border-border bg-card";
          return (
            <span
              key={qid}
              className={`block h-2.5 w-2.5 rounded-full border ${cls}`}
            />
          );
        })}
      </div>
    </div>
  );
}
