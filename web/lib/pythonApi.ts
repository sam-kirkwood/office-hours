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

interface AddInterestArgs {
  userId: string;
  rawText: string;
  addedVia: "survey" | "explicit_request";
}

interface AddInterestResponse {
  node_id: string;
  node_slug: string;
  verdict: string;
  user_interest_id: string;
}

interface UpdateQueueArgs {
  userId: string;
}

interface UpdateQueueResponse {
  ok: boolean;
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

export async function addInterest(
  args: AddInterestArgs,
): Promise<AddInterestResponse> {
  return pythonPost("/add-interest", {
    user_id: args.userId,
    raw_text: args.rawText,
    added_via: args.addedVia,
  });
}

export async function updateQueue(
  args: UpdateQueueArgs,
): Promise<UpdateQueueResponse> {
  return pythonPost("/update-queue", { user_id: args.userId });
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
