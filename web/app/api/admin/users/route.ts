import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { assertAdminApi } from "@/lib/adminAuth";

export async function GET() {
  const err = await assertAdminApi();
  if (err) return err;

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const [
    { data: profiles },
    { data: queueItems },
    { data: nodes },
    { data: interests },
  ] = await Promise.all([
    supabaseAdmin
      .from("profiles")
      .select("id, email, display_name, created_at")
      .order("created_at", { ascending: true }),
    supabaseAdmin
      .from("queue_items")
      .select(
        "id, user_id, kind, ref_id, state, priority_score, added_reason, added_at, time_estimate_minutes_low, time_estimate_minutes_high",
      )
      .order("priority_score", { ascending: false }),
    supabaseAdmin.from("nodes").select("id, title"),
    supabaseAdmin.from("user_interests").select("user_id"),
  ]);

  const nodeMap = new Map((nodes ?? []).map((n) => [n.id, n.title as string]));

  const queueByUser = new Map<string, typeof queueItems>();
  for (const item of queueItems ?? []) {
    if (!queueByUser.has(item.user_id)) queueByUser.set(item.user_id, []);
    queueByUser.get(item.user_id)!.push(item);
  }

  const interestCountByUser = new Map<string, number>();
  for (const row of interests ?? []) {
    interestCountByUser.set(
      row.user_id,
      (interestCountByUser.get(row.user_id) ?? 0) + 1,
    );
  }

  const users = (profiles ?? []).map((p) => ({
    ...p,
    interest_count: interestCountByUser.get(p.id) ?? 0,
    queue_items: (queueByUser.get(p.id) ?? []).map((qi) => ({
      ...qi,
      node_title:
        qi.kind === "concept_review" || qi.kind === "suggested_interest"
          ? (nodeMap.get(qi.ref_id ?? "") ?? null)
          : null,
    })),
  }));

  return NextResponse.json({ users });
}
