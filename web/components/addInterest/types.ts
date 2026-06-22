// Shared types for the add-interest dialog and concept tour.
//
// The dialog is used in three contexts (survey-and-difficulty-design.md §2):
//   - Stage 4 onboarding (full-page, sequential per parsed segment)
//   - Daily-tab "Curious about something specific?" (modal)
//   - Skill-tree NodePanel "Add to my interests" + Stage 7 Edit (modal,
//     pre-filled with a known node)

import type {
  NodeReadinessTileDTO,
  ParsedInterestSegmentDTO,
} from "@/lib/pythonApi";

export type AddedVia = "survey" | "explicit_request" | "cross_pollination";

export type DialogPresentation = "full-page" | "modal";

// For Edit / NodePanel flows where we already know the node and want to
// skip /parse. The dialog renders a single optional follow-up (the "what's
// off?" or "what draws you to this?" beat) and then calls /resolve directly
// with existing_node_slug set to preNode.slug.
export interface PreNodeInput {
  slug: string;
  title: string;
  // Pre-fill the followup textarea (e.g. the user's current intent_context).
  defaultIntentContext?: string;
  // Override the mirror_back_md headline. Defaults to a generic line.
  mirrorOverride?: string;
  // Override the followup prompt label.
  followupPromptOverride?: string;
}

export interface DialogResolved {
  user_interest_id: string;
  node_id: string;
  node_slug: string;
  verdict: "same" | "related" | "new";
  intent_context: string;
  starter_preview_md: string;
  // Phase 13 Step 3: node-level readiness pass (replaces concept_tour).
  node_readiness: NodeReadinessTileDTO[];
}

// What the orchestrator hands the Dialog. Either a parsed segment from
// /add-interest/parse (the normal path) or a pre-known node (the Edit /
// NodePanel path).
export type DialogInput =
  | { source: "segment"; segment: ParsedInterestSegmentDTO }
  | { source: "preNode"; preNode: PreNodeInput };
