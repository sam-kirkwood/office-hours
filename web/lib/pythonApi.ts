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
// node). The full dialog UI lives behind these; see Step 2d for the
// post-onboarding panel that exposes the dialog.
//
// `addInterest` below is a backwards-compat shim that runs both calls back
// to back with best-guess inputs. It exists so callers that don't yet route
// users through the dialog UI keep working until Step 2d wires them through.

type AddedVia = "survey" | "explicit_request" | "cross_pollination";

export interface ParsedInterestSegmentDTO {
  raw_text_segment: string;
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

interface AddInterestArgs {
  userId: string;
  rawText: string;
  addedVia: AddedVia;
}

interface AddInterestResponse {
  node_id: string;
  node_slug: string;
  verdict: string;
  user_interest_id: string;
  intent_context: string;
}

interface UpdateQueueArgs {
  userId: string;
  trigger: "attempt_submit" | "engagement_complete" | "interest_add";
  refId?: string;
}

interface UpdateQueueResponse {
  items_reweighted: number;
  refreshers_scheduled: number;
  items_pruned: number;
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

// Best-guess pass-through for callers that don't yet route users through the
// add-interest dialog UI (TODO(2d): replace these call sites with the real
// dialog). Picks the first parsed segment, accepts the dedup verdict, and
// uses the draft intent_context. Returns the same shape the deprecated
// /add-interest endpoint used to return.
export async function addInterest(
  args: AddInterestArgs,
): Promise<AddInterestResponse> {
  const parsed = await parseAddInterest(args);
  if (parsed.segments.length === 0) {
    throw new Error("add-interest parse returned no segments");
  }
  const seg = parsed.segments[0];
  const intentContext = seg.draft_intent_context || seg.mirror_back_md;
  const finalIntentText = seg.raw_text_segment || args.rawText;
  const resolved = await resolveAddInterest({
    userId: args.userId,
    addedVia: args.addedVia,
    rawText: args.rawText,
    finalIntentText,
    intentContext,
    existingNodeSlug: seg.dedup.verdict === "same" ? seg.dedup.matched_node_slug : null,
    relatedNodeSlug: seg.dedup.verdict === "related" ? seg.dedup.matched_node_slug : null,
  });
  return {
    node_id: resolved.node_id,
    node_slug: resolved.node_slug,
    verdict: resolved.verdict,
    user_interest_id: resolved.user_interest_id,
    intent_context: resolved.intent_context,
  };
}

export async function updateQueue(
  args: UpdateQueueArgs,
): Promise<UpdateQueueResponse> {
  return pythonPost("/update-queue", {
    user_id: args.userId,
    trigger: args.trigger,
    ref_id: args.refId ?? null,
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

interface SuggestSurveyInterestsArgs {
  userId: string;
  domainChips: string[];
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
    domain_chips: args.domainChips,
    marked_foundation_node_ids: args.markedFoundationNodeIds,
  });
}
