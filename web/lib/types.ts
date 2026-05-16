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

export type NodeRating = "interested" | "comfortable" | "refresh";
export type NodeRatings = Record<string, NodeRating>; // keyed by node slug

export interface SurveyV2Payload {
  free_text_intent: string;
  node_ratings: NodeRatings;
  comfort_responses: Record<string, string>;
  mode_balance: number;
}

export interface CanonicalTopic {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  difficulty_band: "intro" | "core" | "advanced";
  domain: string;
  subtopics: Subtopic[];
  created_at: string;
}

export interface CanonicalEdge {
  id: string;
  prerequisite_topic_id: string;
  dependent_topic_id: string;
  weight: number;
}

export interface UserPlan {
  id: string;
  user_id: string;
  status: "pending_review" | "active" | "completed";
  adjustment_notes: string | null;
  created_at: string;
}

export interface PlanNode {
  id: string;
  plan_id: string;
  canonical_topic_id: string;
  order_index: number;
  state: "pending" | "active" | "struggling" | "mastered";
  problems_completed_count: number;
  canonical_topics?: CanonicalTopic;
}

export type TopicState = "target" | "known" | "refresher";

export interface TopicEntry {
  state?: TopicState;
  subtopics?: Record<string, TopicState>;
}

export type TopicStateMap = Record<string, TopicEntry>;

export interface SurveyPayload {
  background: {
    degrees: string[];
    yearsSinceStudy: string;
    degreeFields: string;
    currentField: string;
  };
  topicStates: TopicStateMap;
  extraTopics: string;
  difficultyCurve: "gentle" | "standard" | "aggressive";
}

// Phase 3 — daily problem types.
//
// `solution_md` and `rubric_md` are deliberately omitted from the client-shipped
// `Problem` shape: the daily page never needs them, the RLS policy on
// `problems` already restricts access, and dropping them here is defence in
// depth against an accidental over-select.

export interface Problem {
  id: string;
  canonical_topic_id: string | null;
  statement_md: string;
  difficulty: number | null;
  context_hook_id: string | null;
  generated_context_md: string | null;
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

export interface DailyAssignment {
  id: string;
  user_id: string;
  problem_id: string;
  plan_node_id: string | null;
  assigned_for_date: string;
  status: "pending" | "in_progress" | "submitted" | "graded";
}
