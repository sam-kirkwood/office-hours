// Server-only helper that produces (or reuses) today's assignment bundle for
// a user. Wraps the Python `/generate-problem` call and the
// `daily_assignments` insert.
//
// Day-key timezone: this uses the *server's* local TZ. For an SF-based
// operator and friends, that's fine. A future improvement is to persist a
// per-user timezone on `profiles` and pass it in here — see the Step 6
// handoff notes in dev-docs/phase-3-plan.md.

import { createClient } from "@supabase/supabase-js";
import { generateProblem } from "@/lib/pythonApi";
import type {
  ContextHook,
  DailyAssignment,
  Problem,
  ProblemHint,
} from "@/lib/types";

export interface TodaysAssignmentBundle {
  assignment: DailyAssignment;
  problem: Problem;
  hints: ProblemHint[];
  contextHook: ContextHook | null;
}

export type TodaysAssignmentResult =
  | { kind: "ok"; bundle: TodaysAssignmentBundle }
  | { kind: "no_plan" }
  | { kind: "plan_complete" };

const PROBLEM_CLIENT_COLUMNS =
  "id, canonical_topic_id, statement_md, difficulty, context_hook_id, " +
  "generated_context_md, created_at";

function adminClient() {
  if (!process.env.SUPABASE_SECRET_KEY) {
    throw new Error("SUPABASE_SECRET_KEY is not set");
  }
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY,
  );
}

function todayKey(): string {
  // Server-local YYYY-MM-DD. Postgres `date` accepts this directly.
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function isUniqueViolation(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const e = err as { code?: unknown; message?: unknown };
  if (e.code === "23505") return true;
  const message = typeof e.message === "string" ? e.message.toLowerCase() : "";
  return message.includes("duplicate key");
}

async function loadBundle(
  supabase: ReturnType<typeof adminClient>,
  assignment: DailyAssignment,
): Promise<TodaysAssignmentBundle> {
  const { data: problemData, error: problemErr } = await supabase
    .from("problems")
    .select(PROBLEM_CLIENT_COLUMNS)
    .eq("id", assignment.problem_id)
    .single();
  if (problemErr || !problemData) {
    throw new Error(
      `failed to load problem ${assignment.problem_id}: ${problemErr?.message ?? "missing"}`,
    );
  }
  const problem = problemData as unknown as Problem;

  const { data: hints, error: hintsErr } = await supabase
    .from("problem_hints")
    .select("id, problem_id, level, text")
    .eq("problem_id", assignment.problem_id)
    .order("level", { ascending: true });
  if (hintsErr) {
    throw new Error(`failed to load hints: ${hintsErr.message}`);
  }

  let contextHook: ContextHook | null = null;
  if (problem.context_hook_id) {
    const { data: hook } = await supabase
      .from("context_hooks")
      .select(
        "id, slug, title, summary_md, related_topic_ids, difficulty_band, sources_json, created_at",
      )
      .eq("id", problem.context_hook_id)
      .maybeSingle();
    contextHook = (hook as unknown as ContextHook | null) ?? null;
  }

  return {
    assignment,
    problem,
    hints: (hints ?? []) as unknown as ProblemHint[],
    contextHook,
  };
}

export async function ensureTodaysAssignment(
  userId: string,
): Promise<TodaysAssignmentResult> {
  const supabase = adminClient();
  const dayKey = todayKey();

  // Existing assignment for today?
  const { data: existing } = await supabase
    .from("daily_assignments")
    .select("id, user_id, problem_id, plan_node_id, assigned_for_date, status")
    .eq("user_id", userId)
    .eq("assigned_for_date", dayKey)
    .maybeSingle();
  if (existing) {
    return { kind: "ok", bundle: await loadBundle(supabase, existing as DailyAssignment) };
  }

  // Active plan?
  const { data: plan } = await supabase
    .from("user_plans")
    .select("id")
    .eq("user_id", userId)
    .eq("status", "active")
    .maybeSingle();
  if (!plan) return { kind: "no_plan" };

  // Active node, else lowest-order_index pending node.
  const { data: activeNode } = await supabase
    .from("plan_nodes")
    .select("id")
    .eq("plan_id", plan.id)
    .eq("state", "active")
    .order("order_index")
    .limit(1)
    .maybeSingle();

  let planNodeId: string | null = activeNode?.id ?? null;
  if (!planNodeId) {
    const { data: pendingNode } = await supabase
      .from("plan_nodes")
      .select("id")
      .eq("plan_id", plan.id)
      .eq("state", "pending")
      .order("order_index")
      .limit(1)
      .maybeSingle();
    planNodeId = pendingNode?.id ?? null;
  }
  if (!planNodeId) return { kind: "plan_complete" };

  // Generate (or hit cache).
  const { problem_id } = await generateProblem({ userId, planNodeId });

  // Insert; on unique violation, re-select the winner.
  const insertRow = {
    user_id: userId,
    problem_id,
    plan_node_id: planNodeId,
    assigned_for_date: dayKey,
    status: "pending" as const,
  };
  const { data: inserted, error: insertErr } = await supabase
    .from("daily_assignments")
    .insert(insertRow)
    .select("id, user_id, problem_id, plan_node_id, assigned_for_date, status")
    .single();

  let assignment: DailyAssignment;
  if (insertErr && isUniqueViolation(insertErr)) {
    const { data: winner } = await supabase
      .from("daily_assignments")
      .select("id, user_id, problem_id, plan_node_id, assigned_for_date, status")
      .eq("user_id", userId)
      .eq("assigned_for_date", dayKey)
      .single();
    assignment = winner as DailyAssignment;
  } else if (insertErr || !inserted) {
    throw new Error(
      `failed to insert daily_assignment: ${insertErr?.message ?? "no row returned"}`,
    );
  } else {
    assignment = inserted as DailyAssignment;
  }

  return { kind: "ok", bundle: await loadBundle(supabase, assignment) };
}
