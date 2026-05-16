// Server-side client for the Python FastAPI service.
//
// Single shared bearer token (`INTERNAL_API_TOKEN`) is fine for the trusted
// user base — see dev-docs/phase-3-plan.md §"Decisions locked in".

interface GenerateProblemArgs {
  userId: string;
  planNodeId: string;
}

interface GenerateProblemResponse {
  problem_id: string;
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
    plan_node_id: args.planNodeId,
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
