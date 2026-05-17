import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { assertAdminApi } from "@/lib/adminAuth";

interface CostEntry {
  id: string;
  route: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  created_at: string;
  user_id: string | null;
}

interface CostSummary {
  total_cost_usd: number;
  total_calls: number;
  by_route: { route: string; calls: number; cost: number }[];
  by_model: { model: string; calls: number; cost: number }[];
  entries: CostEntry[];
}

export async function GET(request: Request) {
  const err = await assertAdminApi();
  if (err) return err;

  const { searchParams } = new URL(request.url);
  const period = searchParams.get("period") ?? "30d";

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  let query = supabaseAdmin
    .from("llm_calls")
    .select("id, route, model, input_tokens, output_tokens, estimated_cost_usd, created_at, user_id")
    .order("created_at", { ascending: false });

  if (period === "7d") {
    const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    query = query.gte("created_at", cutoff);
  } else if (period === "30d") {
    const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    query = query.gte("created_at", cutoff);
  }
  // period === "all" → no filter

  const { data: entries, error } = await query;
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const rows = (entries ?? []) as CostEntry[];

  const total_cost_usd = rows.reduce((sum, r) => sum + (r.estimated_cost_usd ?? 0), 0);
  const total_calls = rows.length;

  const routeMap = new Map<string, { calls: number; cost: number }>();
  const modelMap = new Map<string, { calls: number; cost: number }>();

  for (const r of rows) {
    const routeKey = r.route ?? "(unknown)";
    const prev = routeMap.get(routeKey) ?? { calls: 0, cost: 0 };
    routeMap.set(routeKey, { calls: prev.calls + 1, cost: prev.cost + (r.estimated_cost_usd ?? 0) });

    const modelKey = r.model ?? "(unknown)";
    const prevM = modelMap.get(modelKey) ?? { calls: 0, cost: 0 };
    modelMap.set(modelKey, { calls: prevM.calls + 1, cost: prevM.cost + (r.estimated_cost_usd ?? 0) });
  }

  const by_route = [...routeMap.entries()]
    .map(([route, v]) => ({ route, ...v }))
    .sort((a, b) => b.cost - a.cost);

  const by_model = [...modelMap.entries()]
    .map(([model, v]) => ({ model, ...v }))
    .sort((a, b) => b.cost - a.cost);

  const summary: CostSummary = {
    total_cost_usd,
    total_calls,
    by_route,
    by_model,
    entries: rows,
  };

  return NextResponse.json(summary);
}
