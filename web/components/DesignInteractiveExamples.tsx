"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ChevronDown, Info } from "lucide-react";

export function DialogExample() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Open dialog</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Submit solution</DialogTitle>
          <DialogDescription>
            Your handwritten solution will be parsed and reviewed before grading.
          </DialogDescription>
        </DialogHeader>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Once submitted, your solution is saved to the notebook. You can dispute
          the feedback later if you disagree with the assessment.
        </p>
        <DialogFooter>
          <Button variant="ghost">Cancel</Button>
          <Button>Submit</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function DropdownExample() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          Actions <ChevronDown className="ml-1 size-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuLabel>Problem</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Request easier version</DropdownMenuItem>
        <DropdownMenuItem>Request harder version</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem>Mark as refreshed</DropdownMenuItem>
        <DropdownMenuItem className="text-destructive">Skip</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function TooltipExample() {
  return (
    <div className="flex items-center gap-3">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon">
            <Info className="size-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Hints are pre-generated. They guide, never solve.</p>
        </TooltipContent>
      </Tooltip>
      <span className="text-sm text-muted-foreground">Hover the info icon</span>
    </div>
  );
}

// Candidate stylings for the notebook's by-interest tab strip. The live
// version uses a horizontally-scrolling underline strip whose native scrollbar
// reads as "gross"; these are alternatives to pick from. Each is interactive
// and constrained to a notebook-ish column width so overflow/wrap is visible.
const NB_TABS = [
  "All",
  "Quantum Mechanics",
  "Cosmology & ΛCDM",
  "Fourier Analysis",
  "Statistical Mechanics",
  "Differential Equations",
  "Come back to this",
];
const NB_COMEBACK = "Come back to this";

function CountBadge({ n }: { n: number }) {
  return (
    <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
      {n}
    </span>
  );
}

function OptionFrame({
  label,
  note,
  children,
}: {
  label: string;
  note: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-semibold uppercase tracking-widest text-foreground">
          {label}
        </span>
        <span className="text-xs text-muted-foreground">{note}</span>
      </div>
      <div className="max-w-md rounded-md border border-border bg-card p-4">
        {children}
        <p className="mt-4 font-serif text-sm leading-relaxed text-muted-foreground">
          Entries for the selected tab would appear here.
        </p>
      </div>
    </div>
  );
}

export function NotebookTabsOptions() {
  const [a, setA] = useState(NB_TABS[0]);
  const [b, setB] = useState(NB_TABS[0]);
  const [c, setC] = useState(NB_TABS[0]);
  const [d, setD] = useState(NB_TABS[0]);

  const pill = (active: boolean) =>
    `shrink-0 rounded-full border px-3 py-1 text-sm transition-colors duration-[var(--duration-fast)] ${
      active
        ? "border-amber/50 bg-[var(--amber-subtle)] text-foreground"
        : "border-border text-muted-foreground hover:text-foreground"
    }`;

  const underline = (active: boolean) =>
    `shrink-0 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors duration-[var(--duration-fast)] ${
      active
        ? "border-primary font-medium text-foreground"
        : "border-transparent text-muted-foreground hover:text-foreground"
    }`;

  const cInterests = NB_TABS.filter((t) => t !== "All" && t !== NB_COMEBACK);
  const cInterestActive = c !== "All" && c !== NB_COMEBACK;

  return (
    <div className="space-y-7">
      {/* A — wrapping pills */}
      <OptionFrame label="Option A" note="Wrapping pills — no scroll, chips flow onto new rows">
        <div className="flex flex-wrap gap-2">
          {NB_TABS.map((t) => (
            <button key={t} type="button" onClick={() => setA(t)} className={pill(a === t)}>
              {t}
              {t === NB_COMEBACK && <CountBadge n={3} />}
            </button>
          ))}
        </div>
      </OptionFrame>

      {/* B — wrapping underline tabs */}
      <OptionFrame label="Option B" note="Wrapping underline tabs — same family as current, but wraps">
        <div className="flex flex-wrap items-center gap-x-1">
          {NB_TABS.map((t) => (
            <button key={t} type="button" onClick={() => setB(t)} className={underline(b === t)}>
              {t}
              {t === NB_COMEBACK && <CountBadge n={3} />}
            </button>
          ))}
        </div>
      </OptionFrame>

      {/* C — fixed tabs + interest dropdown */}
      <OptionFrame label="Option C" note="Fixed tabs + a Topics dropdown — minimal chrome, scales to many interests">
        <div className="flex items-center gap-1 border-b border-border">
          <button type="button" onClick={() => setC("All")} className={underline(c === "All")}>
            All
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className={`flex items-center gap-1 ${underline(cInterestActive)}`}
              >
                {cInterestActive ? c : "Topics"}
                <ChevronDown className="size-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
              {cInterests.map((t) => (
                <DropdownMenuItem key={t} onClick={() => setC(t)}>
                  {t}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <button
            type="button"
            onClick={() => setC(NB_COMEBACK)}
            className={underline(c === NB_COMEBACK)}
          >
            {NB_COMEBACK}
            <CountBadge n={3} />
          </button>
        </div>
      </OptionFrame>

      {/* D — hidden-scrollbar strip (current behaviour, scrollbar removed) */}
      <OptionFrame label="Option D" note="Current scrolling strip with the scrollbar hidden — swipe / shift-scroll / drag">
        <div className="overflow-x-auto border-b border-border [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <div className="flex w-max items-center gap-1">
            {NB_TABS.map((t) => (
              <button key={t} type="button" onClick={() => setD(t)} className={underline(d === t)}>
                {t}
                {t === NB_COMEBACK && <CountBadge n={3} />}
              </button>
            ))}
          </div>
        </div>
      </OptionFrame>
    </div>
  );
}

export function HintPanel() {
  const [openHint, setOpenHint] = useState<number | null>(null);

  const hints = [
    {
      level: 1,
      label: "Nudge",
      text: "Consider what happens when you differentiate both sides of the equation f′(x) = f(x). What does this tell you about f″?",
    },
    {
      level: 2,
      label: "Direction",
      text: "If g(x) = f(x)·e^{−x}, what is g′(x)? Use the product rule.",
    },
    {
      level: 3,
      label: "Structure",
      text: "Once you have g′(x) = 0, conclude that g is constant. Then use the initial condition f(0) = 1 to find that constant.",
    },
  ];

  return (
    <div className="space-y-1.5">
      {hints.map((hint) => (
        <div key={hint.level} className="rounded-md border border-border overflow-hidden">
          <button
            onClick={() => setOpenHint(openHint === hint.level ? null : hint.level)}
            className="flex w-full items-center justify-between px-3.5 py-2.5 text-left text-sm font-medium text-foreground hover:bg-accent transition-colors duration-[var(--duration-fast)]"
          >
            <span>
              <span className="text-muted-foreground mr-2">Hint {hint.level}.</span>
              {hint.label}
            </span>
            <ChevronDown
              className={`size-3.5 text-muted-foreground transition-transform duration-[var(--duration-standard)] ${
                openHint === hint.level ? "rotate-180" : ""
              }`}
            />
          </button>
          {openHint === hint.level && (
            <div className="px-3.5 pb-3 pt-0">
              <p className="text-sm text-muted-foreground leading-relaxed font-serif">
                {hint.text}
              </p>
            </div>
          )}
        </div>
      ))}
      <p className="text-xs text-muted-foreground pt-1">
        Hints are progressive. Each builds on the last.
      </p>
    </div>
  );
}
