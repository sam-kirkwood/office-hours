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

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

export async function generateProblem(
  args: GenerateProblemArgs,
): Promise<GenerateProblemResponse> {
  const baseUrl = requireEnv("PYTHON_API_URL");
  const token = requireEnv("INTERNAL_API_TOKEN");

  const res = await fetch(`${baseUrl}/generate-problem`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      user_id: args.userId,
      plan_node_id: args.planNodeId,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `generate-problem failed: ${res.status} ${res.statusText} — ${body}`,
    );
  }

  return (await res.json()) as GenerateProblemResponse;
}
