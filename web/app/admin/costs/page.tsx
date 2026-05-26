import { createClient } from "@supabase/supabase-js";
import Link from "next/link";
import { requireAdmin } from "@/lib/adminAuth";

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

function formatCost(usd: number): string {
  return usd < 0.001 ? "<$0.001" : `$${usd.toFixed(4)}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const PAGE_SIZE = 50;

export default async function CostsPage({
  searchParams,
}: {
  searchParams: Promise<{ period?: string; page?: string }>;
}) {
  await requireAdmin();

  const { period: periodParam, page: pageParam } = await searchParams;
  const period = (periodParam === "7d" || periodParam === "all") ? periodParam : "30d";
  const page = Math.max(1, parseInt(pageParam ?? "1"));

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  let query = supabaseAdmin
    .from("llm_calls")
    .select(
      "id, route, model, input_tokens, output_tokens, estimated_cost_usd, created_at, user_id",
    )
    .order("created_at", { ascending: false });

  if (period === "7d") {
    const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    query = query.gte("created_at", cutoff);
  } else if (period === "30d") {
    const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    query = query.gte("created_at", cutoff);
  }

  const { data } = await query;
  const rows = (data ?? []) as CostEntry[];

  const totalCost = rows.reduce((sum, r) => sum + (r.estimated_cost_usd ?? 0), 0);

  const routeMap = new Map<string, { calls: number; cost: number }>();
  const modelMap = new Map<string, { calls: number; cost: number }>();
  for (const r of rows) {
    const rk = r.route ?? "(unknown)";
    const prev = routeMap.get(rk) ?? { calls: 0, cost: 0 };
    routeMap.set(rk, { calls: prev.calls + 1, cost: prev.cost + (r.estimated_cost_usd ?? 0) });
    const mk = r.model ?? "(unknown)";
    const prevM = modelMap.get(mk) ?? { calls: 0, cost: 0 };
    modelMap.set(mk, { calls: prevM.calls + 1, cost: prevM.cost + (r.estimated_cost_usd ?? 0) });
  }

  const byRoute = [...routeMap.entries()]
    .map(([route, v]) => ({ route, ...v }))
    .sort((a, b) => b.cost - a.cost);

  const byModel = [...modelMap.entries()]
    .map(([model, v]) => ({ model, ...v }))
    .sort((a, b) => b.cost - a.cost);

  const totalRows = rows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  const clampedPage = Math.min(page, totalPages);
  const displayRows = rows.slice((clampedPage - 1) * PAGE_SIZE, clampedPage * PAGE_SIZE);
  const firstRow = totalRows === 0 ? 0 : (clampedPage - 1) * PAGE_SIZE + 1;
  const lastRow = Math.min(clampedPage * PAGE_SIZE, totalRows);

  function pageHref(p: number) {
    const params = new URLSearchParams({ period, page: String(p) });
    return `?${params.toString()}`;
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      {/* Header + period selector */}
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Cost dashboard</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            LLM call costs from the <code className="font-mono text-xs">llm_calls</code> table.
          </p>
        </div>
        <form method="GET" className="flex items-center gap-2">
          <label
            htmlFor="period"
            className="text-xs font-semibold uppercase tracking-widest text-muted-foreground"
          >
            Period
          </label>
          <select
            id="period"
            name="period"
            defaultValue={period}
            className="rounded-md border border-border bg-background px-2 py-1 font-mono text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-[var(--amber)]"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>
          <button
            type="submit"
            className="rounded-md border border-border px-3 py-1 text-sm text-muted-foreground hover:text-foreground"
          >
            Apply
          </button>
        </form>
      </div>

      {/* Summary cards */}
      <div className="mb-10 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div className="rounded-md border border-border bg-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Total calls
          </p>
          <p className="mt-1 font-mono text-2xl text-foreground">{rows.length}</p>
        </div>
        <div className="rounded-md border border-border bg-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Total cost
          </p>
          <p className="mt-1 font-mono text-2xl text-foreground">{formatCost(totalCost)}</p>
        </div>
        <div className="rounded-md border border-border bg-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Avg cost / call
          </p>
          <p className="mt-1 font-mono text-2xl text-foreground">
            {rows.length === 0 ? "—" : formatCost(totalCost / rows.length)}
          </p>
        </div>
      </div>

      {/* Breakdown tables */}
      <div className="mb-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
        {/* By route */}
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            By route
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pb-2 text-left text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Route
                </th>
                <th className="pb-2 text-right text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Calls
                </th>
                <th className="pb-2 text-right text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Cost
                </th>
              </tr>
            </thead>
            <tbody>
              {byRoute.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-3 text-sm text-muted-foreground">
                    No data.
                  </td>
                </tr>
              ) : (
                byRoute.map((r) => (
                  <tr key={r.route} className="border-b border-border/40">
                    <td className="py-2 font-mono text-xs text-muted-foreground">{r.route}</td>
                    <td className="py-2 text-right font-mono text-sm">{r.calls}</td>
                    <td
                      className={`py-2 text-right font-mono text-sm ${r.cost > 0.05 ? "text-[var(--amber)]" : ""}`}
                    >
                      {formatCost(r.cost)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* By model */}
        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            By model
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="pb-2 text-left text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Model
                </th>
                <th className="pb-2 text-right text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Calls
                </th>
                <th className="pb-2 text-right text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Cost
                </th>
              </tr>
            </thead>
            <tbody>
              {byModel.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-3 text-sm text-muted-foreground">
                    No data.
                  </td>
                </tr>
              ) : (
                byModel.map((m) => (
                  <tr key={m.model} className="border-b border-border/40">
                    <td className="py-2 font-mono text-xs text-muted-foreground">{m.model}</td>
                    <td className="py-2 text-right font-mono text-sm">{m.calls}</td>
                    <td
                      className={`py-2 text-right font-mono text-sm ${m.cost > 0.05 ? "text-[var(--amber)]" : ""}`}
                    >
                      {formatCost(m.cost)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Full log */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Full log
            {totalRows > 0 && (
              <span className="ml-2 normal-case font-normal">
                — showing {firstRow}–{lastRow} of {totalRows}
              </span>
            )}
          </h2>
          {totalPages > 1 && (
            <div className="flex items-center gap-2 text-xs">
              {clampedPage > 1 ? (
                <Link
                  href={pageHref(clampedPage - 1)}
                  className="rounded border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground"
                >
                  ← Prev
                </Link>
              ) : (
                <span className="rounded border border-border px-2 py-0.5 text-muted-foreground/40">
                  ← Prev
                </span>
              )}
              <span className="text-muted-foreground">
                {clampedPage} / {totalPages}
              </span>
              {clampedPage < totalPages ? (
                <Link
                  href={pageHref(clampedPage + 1)}
                  className="rounded border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground"
                >
                  Next →
                </Link>
              ) : (
                <span className="rounded border border-border px-2 py-0.5 text-muted-foreground/40">
                  Next →
                </span>
              )}
            </div>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                {["Date", "Route", "Model", "In tokens", "Out tokens", "Cost"].map((h) => (
                  <th
                    key={h}
                    className="pb-2 text-left text-xs font-semibold uppercase tracking-widest text-muted-foreground last:text-right"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-4 text-sm text-muted-foreground">
                    No LLM calls recorded in this period.
                  </td>
                </tr>
              ) : (
                displayRows.map((r) => (
                  <tr key={r.id} className="border-b border-border/40">
                    <td className="py-2 font-mono text-xs text-muted-foreground">
                      {formatDate(r.created_at)}
                    </td>
                    <td className="py-2 font-mono text-xs text-muted-foreground">{r.route}</td>
                    <td className="py-2 font-mono text-xs text-muted-foreground">{r.model}</td>
                    <td className="py-2 font-mono text-sm">{r.input_tokens?.toLocaleString()}</td>
                    <td className="py-2 font-mono text-sm">{r.output_tokens?.toLocaleString()}</td>
                    <td
                      className={`py-2 text-right font-mono text-sm ${(r.estimated_cost_usd ?? 0) > 0.05 ? "text-[var(--amber)]" : ""}`}
                    >
                      {formatCost(r.estimated_cost_usd ?? 0)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
