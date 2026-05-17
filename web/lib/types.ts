export interface Subtopic {
  slug: string;
  title: string;
}

// ---------------------------------------------------------------------------
// v2 graph types
// ---------------------------------------------------------------------------

export interface Node {
  id: string;
  slug: string;
  title: string;
  description_md: string;
  domain: "math" | "physics" | "applied";
  kind: "foundation" | "interest";
  difficulty_hint: "intro" | "core" | "advanced";
  subtopics_json: unknown[];
  pool_status: string;
  created_at: string;
}

export interface Edge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_kind: "prerequisite" | "related";
  weight: number;
  created_at: string;
}

export interface UserNodeState {
  user_id: string;
  node_id: string;
  state: "unseen" | "bookmarked" | "active" | "struggling" | "comfortable";
  engagement_count: number;
  struggle_score: number;
  last_engaged_at: string | null;
}

export interface UserInterest {
  id: string;
  user_id: string;
  node_id: string;
  weight: number;
  added_via: "survey" | "explicit_request" | "cross_pollination";
  created_at: string;
}

export type NodeRating = "interested" | "comfortable" | "refresh";
export type NodeRatings = Record<string, NodeRating>; // keyed by node slug

export interface SurveyV2Payload {
  free_text_intent: string;
  node_ratings: NodeRatings;
  comfort_responses: Record<string, string>;
  mode_balance: number;
}

// ---------------------------------------------------------------------------
// v2 queue types
// ---------------------------------------------------------------------------

export type QueueItemKind =
  | "problem"
  | "paper_engagement"
  | "refresher"
  | "concept_review"
  | "suggested_interest";

export type QueueItemState =
  | "pending"
  | "surfaced"
  | "in_progress"
  | "done"
  | "skipped"
  | "dismissed";

export interface QueueItem {
  id: string;
  user_id: string;
  kind: QueueItemKind;
  ref_id: string | null;
  state: QueueItemState;
  priority_score: number;
  time_estimate_minutes_low: number | null;
  time_estimate_minutes_high: number | null;
  added_reason: string | null;
  added_at: string;
  updated_at: string;
}

export interface SurfacedPick {
  id: string;
  user_id: string;
  queue_item_ids: string[];
  surfaced_at: string;
  replaced_at: string | null;
  chosen_item_id: string | null;
}

export interface SurfacedQueueItem {
  queue_item_id: string;
  kind: string;
  ref_id: string | null;
  added_reason: string | null;
  time_estimate_minutes_low: number | null;
  time_estimate_minutes_high: number | null;
  // Set by server for refresher items; used to construct the back-link
  subject_kind?: string | null;
  subject_queue_item_id?: string | null;
}

export interface QueueResult {
  pick_id: string | null;
  items: SurfacedQueueItem[];
  more_coming: boolean;
}

// ---------------------------------------------------------------------------
// Problem types (used in Phase 5-rev problem flow)
// ---------------------------------------------------------------------------

// `solution_md` and `rubric_md` are deliberately omitted: the daily page never
// needs them, and dropping them here is defence in depth against an accidental
// over-select.
export interface Problem {
  id: string;
  topic_node_id: string | null;
  statement_md: string;
  difficulty: number | null;
  context_hook_id: string | null;
  context_md: string | null;
  created_at: string;
}

export interface ProblemHint {
  id: string;
  problem_id: string;
  level: number;
  text: string;
}

export interface ContextHook {
  id: string;
  slug: string;
  title: string;
  summary_md: string;
  related_topic_ids: string[];
  difficulty_band: "intro" | "core" | "advanced";
  sources_json: unknown;
  created_at: string;
}

export interface Attempt {
  id: string;
  user_id: string;
  problem_id: string;
  queue_item_id: string | null;
  raw_image_paths: string[];
  parsed_markdown: string | null;
  user_edited_markdown: string | null;
  hint_levels_used: number[];
  parse_status: string | null;
  parsed_by_llm_call_id: string | null;
  grade_response_md: string | null;
  submitted_at: string | null;
  marked_refreshed: boolean;
  requested_easier: boolean;
  requested_harder: boolean;
  parent_attempt_id: string | null;
  disputed: boolean;
  created_at: string;
}

export interface NotebookEntry {
  id: string;
  user_id: string;
  entry_kind: "problem_attempt" | "paper_engagement";
  ref_id: string;
  title: string;
  topic_node_slugs: string[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Paper types (Phase 6-rev)
// ---------------------------------------------------------------------------

export interface Paper {
  id: string;
  title: string;
  authors_json: string[];
  year: number | null;
  arxiv_id: string | null;
  doi: string | null;
  external_url: string | null;
  abstract_md: string | null;
  created_at: string;
}

export interface PaperQuestion {
  id: string;
  kind: "comprehension" | "critical" | "connective";
  prompt_md: string;
  order: number;
}

export interface PaperEngagement {
  id: string;
  user_id: string;
  paper_id: string;
  why_this_md: string | null;
  orienting_concepts_json: string[];
  questions_json: PaperQuestion[];
  state: "pending" | "in_progress" | "completed";
  current_question_index: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface PaperAnswer {
  id: string;
  engagement_id: string;
  question_id: string;
  user_response_md: string | null;
  claude_response_md: string | null;
  submitted_at: string | null;
}

export interface PaperQaTurn {
  id: string;
  engagement_id: string;
  turn_index: number;
  user_message_md: string;
  claude_response_md: string | null;
  created_at: string;
}
