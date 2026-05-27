// Shared helpers for the per-stage survey API routes (Phase 10-rev Step 2c).
//
// The survey is route-per-stage: /survey/<stage>. The surveys row IS the
// working draft; each stage's POST partially updates it. `completed_stages`
// drives the gate so reload mid-survey resumes at the right place.

import { createClient as createAdminClient, type SupabaseClient } from "@supabase/supabase-js";

export type SurveyStage =
  | "background"
  | "foundations"
  | "interests"
  | "dialog"
  | "balance"
  | "confirm";

export const STAGE_ORDER: SurveyStage[] = [
  "background",
  "foundations",
  "interests",
  "dialog",
  "balance",
  "confirm",
];

export function getAdminClient(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!url || !key) {
    throw new Error("Supabase env vars not set (NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SECRET_KEY)");
  }
  return createAdminClient(url, key);
}

export interface SurveyDomainEntryDraft {
  key: string;
  subareas: string[];
  relationship: string | null;
}

export interface SurveyDraft {
  background_json: { domains: SurveyDomainEntryDraft[] };
  free_text_intent: string;
  node_ratings_json: Record<string, "refresh">;
  pending_interests_json: { tile_slugs?: string[]; free_text?: string };
  mode_balance: number;
  completed_stages: SurveyStage[];
}

export const EMPTY_DRAFT: SurveyDraft = {
  background_json: { domains: [] },
  free_text_intent: "",
  node_ratings_json: {},
  pending_interests_json: {},
  mode_balance: 0.5,
  completed_stages: [],
};

// Accepts the new shape ({domains: []}) and silently upgrades the pre-2c-tweak
// shape ({domain_chips, relationship_cards}) so rows from earlier test runs
// still load. Old shape's relationship_cards[] (a global list) is dropped —
// it can't be re-attributed per-domain reliably.
function normaliseBackground(raw: unknown): { domains: SurveyDomainEntryDraft[] } {
  if (!raw || typeof raw !== "object") return { domains: [] };
  const obj = raw as Record<string, unknown>;
  if (Array.isArray(obj.domains)) {
    const domains = (obj.domains as unknown[])
      .filter((d): d is Record<string, unknown> => !!d && typeof d === "object")
      .map((d) => ({
        key: String(d.key ?? ""),
        subareas: Array.isArray(d.subareas)
          ? (d.subareas as unknown[]).filter((s): s is string => typeof s === "string")
          : [],
        relationship: typeof d.relationship === "string" ? d.relationship : null,
      }))
      .filter((d) => d.key.length > 0);
    return { domains };
  }
  // Upgrade the pre-tweak shape: one entry per chip, no sub-areas, no
  // relationship (the old global cards aren't safely per-domain).
  const chips = Array.isArray(obj.domain_chips) ? obj.domain_chips : [];
  return {
    domains: chips
      .filter((c): c is string => typeof c === "string")
      .map((key) => ({ key, subareas: [], relationship: null })),
  };
}

export async function loadSurveyDraft(
  admin: SupabaseClient,
  userId: string,
): Promise<SurveyDraft> {
  const { data } = await admin
    .from("surveys")
    .select(
      "background_json, free_text_intent, node_ratings_json, pending_interests_json, mode_balance, completed_stages",
    )
    .eq("user_id", userId)
    .maybeSingle();
  if (!data) return { ...EMPTY_DRAFT, background_json: { domains: [] } };
  return {
    background_json: normaliseBackground(data.background_json),
    free_text_intent: data.free_text_intent ?? "",
    node_ratings_json: data.node_ratings_json ?? {},
    pending_interests_json: data.pending_interests_json ?? {},
    mode_balance: data.mode_balance ?? 0.5,
    completed_stages: (data.completed_stages ?? []) as SurveyStage[],
  };
}

// Returns the first stage the user should be on right now. Used by the
// /survey route to redirect into the right page, and by each stage page to
// gate against skipping ahead.
export function nextStage(completed: SurveyStage[]): SurveyStage | "done" {
  for (const stage of STAGE_ORDER) {
    if (!completed.includes(stage)) return stage;
  }
  return "done";
}

// For a given stage, what's the earliest stage the user should be on instead?
// Returns null if the user is allowed on this stage.
export function gateFor(
  target: SurveyStage,
  completed: SurveyStage[],
): SurveyStage | "done" | null {
  const next = nextStage(completed);
  if (next === "done") return "done";
  const targetIdx = STAGE_ORDER.indexOf(target);
  const nextIdx = STAGE_ORDER.indexOf(next);
  // Allowed if next == target (just landed on it) or next is later than target
  // (revisiting a stage we already completed).
  if (nextIdx >= targetIdx) return null;
  return next;
}

// Idempotent upsert + mark-complete. Pass only the columns this stage owns.
export async function upsertSurveyStage(
  admin: SupabaseClient,
  userId: string,
  stage: SurveyStage,
  patch: Record<string, unknown>,
): Promise<void> {
  const { data: existing } = await admin
    .from("surveys")
    .select("completed_stages")
    .eq("user_id", userId)
    .maybeSingle();

  const completed: string[] = existing?.completed_stages ?? [];
  const nextCompleted = completed.includes(stage) ? completed : [...completed, stage];

  const row = {
    user_id: userId,
    ...patch,
    completed_stages: nextCompleted,
    updated_at: new Date().toISOString(),
  };

  const { error } = await admin.from("surveys").upsert(row, { onConflict: "user_id" });
  if (error) throw new Error(`surveys upsert failed: ${error.message}`);
}
