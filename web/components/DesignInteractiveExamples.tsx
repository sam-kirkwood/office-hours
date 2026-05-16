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
