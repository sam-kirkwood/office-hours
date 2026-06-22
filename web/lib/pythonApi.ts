// Server-side client for the Python FastAPI service.
//
// Single shared bearer token (`INTERNAL_API_TOKEN`) is fine for the trusted
// user base — see dev-docs/phase-3-plan.md §"Decisions locked in".

interface GenerateProblemArgs {
  userId: string;
  nodeId: string;  // replaces planNodeId
}

interface GenerateProblemResponse {
  problem_id: string;
  queue_item_id: string;
}

interface ParseSolutionArgs {
  userId: string;
  attemptId: string;
  imageUrls: string[];
}

interface ParseSolutionResponse {
  attempt_id: string;
  parsed_markdown: string;
  parse_status: string;
}

interface GradeSolutionArgs {
  userId: string;
  attemptId: string;
  userEditedMarkdown: string;
}

interface GradeSolutionResponse {
  grade_response_md: string;
  notebook_entry_id: string;
}

// ---------------------------------------------------------------------------
// Add-interest dialog (survey-and-difficulty-design.md §2)
// ---------------------------------------------------------------------------
//
// Two-step API: /add-interest/parse (read-only Haiku call) then
// /add-interest/resolve (writes user_interests, optionally generates a new
// node). User-facing entry points run the full dialog
// (web/components/addInterest/Dialog.tsx). Headless callers that already
// have implicit user consent (e.g. /api/queue/request resolving a typed
// topic to a node) call both endpoints back-to-back with the draft
// intent_context — see headlessResolveToNode in
// web/app/api/queue/request/route.ts.

type AddedVia = "survey" | "explicit_request" | "cross_pollination";

// Structured path facts persisted as path_json on user_interests.
// draft_intent_context is excluded — it is narrative prose used only
// to build intent_context and is not stored in path_json.
export interface RichPath {
  key: string;
  label_md: string;
  what_you_learn: string;
  endpoint: string;
  math_intensity: "algebra" | "calculus" | "linear_algebra" | "heavy_math" | "qualitative";
  mode_lean: "problems" | "papers" | "balanced";
  leans_on_prereq_slugs: string[];
}

export interface ParsedInterestSegmentDTO {
  raw_text_segment: string;
  kind: "interest" | "concept";
  specificity: "specific" | "ambiguous";
  implicit_intent: "teach" | "refresh" | "consolidate";
  mirror_back_md: string;
  optional_followup_md: string | null;
  path_options: Array<RichPath & { draft_intent_context: string }>;
  dedup: {
    verdict: "same" | "related" | "new";
    matched_node_slug: string | null;
  };
  draft_intent_context: string;
}

interface ParseAddInterestArgs {
  userId: string;
  rawText: string;
  addedVia: AddedVia;
}

interface ParseAddInterestResponse {
  segments: ParsedInterestSegmentDTO[];
}

// Per-interest altitude signal (Phase 13 Step 3). Drives intent + entry-lane.
export type Altitude = "new" | "coming_back" | "go_deep";

interface ResolveAddInterestArgs {
  userId: string;
  addedVia: AddedVia;
  rawText: string;
  finalIntentText: string;
  intentContext: string;
  existingNodeSlug?: string | null;
  relatedNodeSlug?: string | null;
  pathJson?: RichPath | null;
  altitude?: Altitude | null;
}

// Node-level readiness tile (Phase 13 Step 3) — replaces the subtopic
// ConceptTour. One tile per prerequisite node; the user marks each node's
// overall readiness (solid/rusty/new).
export interface NodeReadinessTileDTO {
  node_id: string;
  node_slug: string;
  node_title: string;
  node_description_preview: string | null;
}

interface ResolveAddInterestResponse {
  user_interest_id: string;
  node_id: string;
  node_slug: string;
  verdict: "same" | "related" | "new";
  intent_context: string;
  starter_preview_md: string;
  node_readiness: NodeReadinessTileDTO[];
}

export type NodeReadinessState = "solid" | "rusty" | "new";

interface SubmitNodeReadinessArgs {
  userId: string;
  userInterestId: string;
  nodeStates: Array<{ nodeId: string; state: NodeReadinessState }>;
}

interface SurfacedItemRaw {
  queue_item_id: string;
  kind: string;
  ref_id: string | null;
  added_reason: string | null;
  time_estimate_minutes_low: number | null;
  time_estimate_minutes_high: number | null;
  via_refresher?: boolean;
  pinned?: boolean;
}

interface SurfaceDailyArgs {
  userId: string;
  // §A5 steering hint — re-picks from the pending pool under a constraint.
  steer?: "shorter" | "more_papers" | "different" | "less_topic";
  steerExcludedRefIds?: string[];  // for "different"
  steerTopicNodeId?: string;       // for "less_topic"
}

interface SurfaceDailyResponse {
  pick_id: string;
  items: SurfacedItemRaw[];
  pending_remaining?: number;
}

// Non-terminal stock below which we fire a background planner refill so the
// queue stays stocked between daily-cron runs (curriculum-curator-design
// §11.4 refill-on-drain; cap is 15, refill trigger is 6).
const REFILL_THRESHOLD = 6;

// Fire-and-forget a planner refill when the user's queue is running low. Safe
// to call from any surface path — it no-ops above the threshold and never
// blocks the caller.
export function maybeRefillQueue(userId: string, pendingRemaining: number): void {
  if (pendingRemaining >= REFILL_THRESHOLD) return;
  planQueue({ userId, triggeredBy: "manual" }).catch((err) =>
    console.error("refill planQueue failed:", err),
  );
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

async function pythonPost<T>(path: string, body: unknown): Promise<T> {
  const baseUrl = requireEnv("PYTHON_API_URL");
  const token = requireEnv("INTERNAL_API_TOKEN");

  const res = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} failed: ${res.status} ${res.statusText} — ${text}`);
  }

  return (await res.json()) as T;
}

export async function generateProblem(
  args: GenerateProblemArgs,
): Promise<GenerateProblemResponse> {
  return pythonPost("/generate-problem", {
    user_id: args.userId,
    node_id: args.nodeId,
  });
}

export async function parseSolution(
  args: ParseSolutionArgs,
): Promise<ParseSolutionResponse> {
  return pythonPost("/parse-solution", {
    user_id: args.userId,
    attempt_id: args.attemptId,
    image_urls: args.imageUrls,
  });
}

export async function gradeSolution(
  args: GradeSolutionArgs,
): Promise<GradeSolutionResponse> {
  return pythonPost("/grade-solution", {
    user_id: args.userId,
    attempt_id: args.attemptId,
    user_edited_markdown: args.userEditedMarkdown,
  });
}

export async function parseAddInterest(
  args: ParseAddInterestArgs,
): Promise<ParseAddInterestResponse> {
  return pythonPost("/add-interest/parse", {
    user_id: args.userId,
    raw_text: args.rawText,
    added_via: args.addedVia,
  });
}

export async function resolveAddInterest(
  args: ResolveAddInterestArgs,
): Promise<ResolveAddInterestResponse> {
  return pythonPost("/add-interest/resolve", {
    user_id: args.userId,
    added_via: args.addedVia,
    raw_text: args.rawText,
    final_intent_text: args.finalIntentText,
    intent_context: args.intentContext,
    existing_node_slug: args.existingNodeSlug ?? null,
    related_node_slug: args.relatedNodeSlug ?? null,
    path_json: args.pathJson ?? null,
    altitude: args.altitude ?? null,
  });
}

// Phase 13 Step 3: write node-level readiness (solid/rusty/new) from the
// coarse calibration pass that replaced the subtopic concept tour. Returns
// 204 with no body.
export async function submitNodeReadiness(
  args: SubmitNodeReadinessArgs,
): Promise<void> {
  await pythonPost("/add-interest/node-readiness", {
    user_id: args.userId,
    user_interest_id: args.userInterestId,
    node_states: args.nodeStates.map((s) => ({
      node_id: s.nodeId,
      state: s.state,
    })),
  });
}

interface RunDailyPlannerArgs {
  userId: string;
  triggeredBy?: "cron" | "cold_start" | "manual";
}

interface RunDailyPlannerResponse {
  job_run_id: string;
  plan_queue_status: "ok" | "error" | "skipped";
  plan_queue_items_added: number;
  plan_queue_items_reprioritised: number;
  plan_queue_items_skipped: number;
  check_deferred_requeued: number;
  check_deferred_kept: number;
  error_message: string | null;
}

// The curator's per-user daily entry point. Wraps /plan-queue + /check-deferred
// and writes a curator_job_runs row. Used by:
//   - Stage 7 survey complete (triggeredBy='cold_start')
//   - Cross-pollination accept (triggeredBy='manual' — outside the daily cron)
//   - pg_cron daily fan-out calls this directly via pg_net (not through here)
export async function planQueue(
  args: RunDailyPlannerArgs,
): Promise<RunDailyPlannerResponse> {
  return pythonPost("/run-daily-planner", {
    user_id: args.userId,
    triggered_by: args.triggeredBy ?? "manual",
  });
}

export async function surfaceDaily(
  args: SurfaceDailyArgs,
): Promise<SurfaceDailyResponse> {
  const res = await pythonPost<SurfaceDailyResponse>("/surface-daily", {
    user_id: args.userId,
    ...(args.steer && { steer: args.steer }),
    ...(args.steerExcludedRefIds && { steer_excluded_ref_ids: args.steerExcludedRefIds }),
    ...(args.steerTopicNodeId && { steer_topic_node_id: args.steerTopicNodeId }),
  });
  maybeRefillQueue(args.userId, res.pending_remaining ?? 0);
  return res;
}

interface SuggestPapersArgs {
  userId: string;
}

interface SuggestPapersResponse {
  suggested: Array<{ paper_id: string; queue_item_id: string }>;
}

export async function suggestPapers(
  args: SuggestPapersArgs,
): Promise<SuggestPapersResponse> {
  return pythonPost("/suggest-papers", { user_id: args.userId });
}

interface IngestPaperArgs {
  userId: string;
  rawInput: string;
}

interface IngestPaperResponse {
  paper_id: string;
  queue_item_id: string;
  created: boolean;
  engagement_id: string;
}

export async function ingestPaper(
  args: IngestPaperArgs,
): Promise<IngestPaperResponse> {
  return pythonPost("/ingest-paper-user", {
    user_id: args.userId,
    raw_input: args.rawInput,
  });
}

interface ConceptReviewResolveArgs {
  userId: string;
  queueItemId: string;
}

export interface ConceptReviewNodeReading {
  id: string;
  slug: string;
  title: string;
  description_md: string;
  subtopics_json: Array<{ slug: string; title: string; gloss_md?: string }>;
  brief_md: string | null;
}

export interface ConceptReviewResolveResponse {
  kind: "problem" | "reading";
  queue_item_id: string | null;
  node: ConceptReviewNodeReading | null;
}

export async function conceptReviewResolve(
  args: ConceptReviewResolveArgs,
): Promise<ConceptReviewResolveResponse> {
  return pythonPost("/concept-review-resolve", {
    user_id: args.userId,
    queue_item_id: args.queueItemId,
  });
}

interface CreateRefresherArgs {
  userId: string;
  // A refresher_schedule.id (legacy: revisit a prior attempt/paper) or a
  // nodes.id (curator-style: pool-first refresh-intent problem).
  refId: string;
  reason?: string | null;
  priorityScore?: number | null;
  parentQueueItemId?: string | null;
}

export interface CreateRefresherResponse {
  // The resolved item's content kind — the caller routes by it.
  kind: "problem" | "paper_engagement" | "concept_review";
  queue_item_id: string;
}

// Resolve an on-demand refresher to a concrete, directly-routable queue item
// (via_refresher=true). Used by the queue request route (a paper orienting
// concept or a skill-tree node). The curator's in-process callers resolve
// directly in Python; this is the only HTTP entry point.
export async function createRefresher(
  args: CreateRefresherArgs,
): Promise<CreateRefresherResponse> {
  return pythonPost("/create-refresher", {
    user_id: args.userId,
    ref_id: args.refId,
    reason: args.reason ?? null,
    priority_score: args.priorityScore ?? null,
    parent_queue_item_id: args.parentQueueItemId ?? null,
  });
}

interface GenerateEdgeDescriptionArgs {
  userId: string;
  edgeId: string;
}

interface GenerateEdgeDescriptionResponse {
  description_md: string;
  cached: boolean;
}

export async function generateEdgeDescription(
  args: GenerateEdgeDescriptionArgs,
): Promise<GenerateEdgeDescriptionResponse> {
  return pythonPost("/generate-edge-description", {
    user_id: args.userId,
    edge_id: args.edgeId,
  });
}

interface ProposePapersArgs {
  userId: string;
  modeBalance?: number;
}

interface ProposePapersResponse {
  papers_added: number;
  papers_reused: number;
  queue_items_added: number;
}

export async function proposePapers(
  args: ProposePapersArgs,
): Promise<ProposePapersResponse> {
  return pythonPost("/propose-papers", {
    user_id: args.userId,
    mode_balance: args.modeBalance ?? 0.5,
  });
}

interface GenerateCurationReportResponse {
  proposals_created: number;
  since: string;
}

export async function generateCurationReport(): Promise<GenerateCurationReportResponse> {
  return pythonPost("/generate-curation-report", {});
}

export interface SurveyInterestSuggestion {
  node_id: string;
  slug: string;
  title: string;
  description_md: string;
  why_suggested_md: string;
}

export interface SurveyDomainInput {
  key: string;
  label: string;
  subareaLabels: string[];
  relationshipLabel: string | null;
}

interface SuggestSurveyInterestsArgs {
  userId: string;
  domains: SurveyDomainInput[];
  markedFoundationNodeIds: string[];
}

interface SuggestSurveyInterestsResponse {
  suggestions: SurveyInterestSuggestion[];
}

export async function suggestSurveyInterests(
  args: SuggestSurveyInterestsArgs,
): Promise<SuggestSurveyInterestsResponse> {
  return pythonPost("/survey/suggest-interests", {
    user_id: args.userId,
    domains: args.domains.map((d) => ({
      key: d.key,
      label: d.label,
      subarea_labels: d.subareaLabels,
      relationship_label: d.relationshipLabel,
    })),
    marked_foundation_node_ids: args.markedFoundationNodeIds,
  });
}

// ---------------------------------------------------------------------------
// Rewrite tag-soup intent_context into user-facing prose. Backfill for the
// profile page. One batch Haiku call per request.

export interface RewriteSummaryItem {
  user_interest_id: string;
  node_title: string;
  node_description_md?: string | null;
  subtopics?: string[];
  current_context: string;
}

interface RewriteIntentSummariesArgs {
  userId: string;
  items: RewriteSummaryItem[];
}

interface RewriteIntentSummariesResponse {
  summaries: Array<{ user_interest_id: string; summary: string }>;
}

export async function rewriteIntentSummaries(
  args: RewriteIntentSummariesArgs,
): Promise<RewriteIntentSummariesResponse> {
  return pythonPost("/add-interest/rewrite-summaries", {
    user_id: args.userId,
    items: args.items,
  });
}

// ---------------------------------------------------------------------------
// /generate-sibling (Phase 12 Step 3 — §A3 correction loop)

export type SiblingKind = "easier" | "harder" | "assume_less";

interface GenerateSiblingArgs {
  userId: string;
  queueItemId: string;
  kind: SiblingKind;
}

export interface GenerateSiblingResponse {
  sibling_problem_id: string | null;
  sibling_queue_item_id: string | null;
  is_max_difficulty: boolean;
  is_min_difficulty: boolean;
}

export async function generateSibling(
  args: GenerateSiblingArgs,
): Promise<GenerateSiblingResponse> {
  return pythonPost("/generate-sibling", {
    user_id: args.userId,
    queue_item_id: args.queueItemId,
    kind: args.kind,
  });
}

// ---------------------------------------------------------------------------
// /curiosity-box (Phase 12 Step 4c — §A4 classifier + routes)

interface CuriosityBoxArgs {
  userId: string;
  rawText: string;
}

export type CuriosityBoxAction =
  | "redirect_steer"
  | "redirect_feedback"
  | "graceful"
  | "topic_new_stub"
  | "topic_new_explored"
  | "answer"
  | "ingest_paper"
  | "queued_pinned"
  | "clarify";

export interface CuriosityBoxResponse {
  action: CuriosityBoxAction;
  message_md: string;
  answer_md?: string | null;
  followon_topic_hint?: string | null;
  queue_item_id?: string | null;
  paper_ref?: string | null;
  topic_hint?: string | null;
  clarification_md?: string | null;
}

export async function handleCuriosityBox(
  args: CuriosityBoxArgs,
): Promise<CuriosityBoxResponse> {
  return pythonPost("/curiosity-box", {
    user_id: args.userId,
    raw_text: args.rawText,
  });
}
