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

export interface ParsedInterestSegmentDTO {
  raw_text_segment: string;
  kind: "interest" | "concept";
  specificity: "specific" | "ambiguous";
  implicit_intent: "teach" | "refresh" | "consolidate";
  mirror_back_md: string;
  optional_followup_md: string | null;
  path_options: Array<{
    key: string;
    label_md: string;
    draft_intent_context: string;
  }>;
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

interface ResolveAddInterestArgs {
  userId: string;
  addedVia: AddedVia;
  rawText: string;
  finalIntentText: string;
  intentContext: string;
  existingNodeSlug?: string | null;
  relatedNodeSlug?: string | null;
}

export interface ConceptTourTileDTO {
  node_id: string;
  node_slug: string;
  subtopic_key: string;
  name: string;
  gloss: string | null;
}

interface ResolveAddInterestResponse {
  user_interest_id: string;
  node_id: string;
  node_slug: string;
  verdict: "same" | "related" | "new";
  intent_context: string;
  starter_preview_md: string;
  concept_tour: ConceptTourTileDTO[];
}

interface SurfacedItemRaw {
  queue_item_id: string;
  kind: string;
  ref_id: string | null;
  added_reason: string | null;
  time_estimate_minutes_low: number | null;
  time_estimate_minutes_high: number | null;
}

interface SurfaceDailyArgs {
  userId: string;
}

interface SurfaceDailyResponse {
  pick_id: string;
  items: SurfacedItemRaw[];
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
  return pythonPost("/surface-daily", { user_id: args.userId });
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
  subtopics_json: Array<{ slug: string; title: string }>;
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

interface ProposePapersArgs {
  userId: string;
}

interface ProposePapersResponse {
  papers_added: number;
  papers_reused: number;
  queue_items_added: number;
}

export async function proposePapers(
  args: ProposePapersArgs,
): Promise<ProposePapersResponse> {
  return pythonPost("/propose-papers", { user_id: args.userId });
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
