import { createClient } from "@supabase/supabase-js";
import { requireAdmin } from "@/lib/adminAuth";
import { UserQueueCard } from "@/components/UserQueueCard";

export default async function UsersPage() {
  await requireAdmin();

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
      .select("id, user_id, kind, ref_id, state, priority_score, added_reason")
      .neq("state", "dismissed")
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
    interestCountByUser.set(row.user_id, (interestCountByUser.get(row.user_id) ?? 0) + 1);
  }

  const users = (profiles ?? []).map((p) => ({
    ...p,
    interest_count: interestCountByUser.get(p.id) ?? 0,
    queue: (queueByUser.get(p.id) ?? []).map((qi) => ({
      id: qi.id,
      kind: qi.kind,
      state: qi.state,
      priority_score: qi.priority_score,
      added_reason: qi.added_reason,
      node_title:
        qi.kind === "concept_review" || qi.kind === "suggested_interest"
          ? (nodeMap.get(qi.ref_id ?? "") ?? null)
          : null,
    })),
  }));

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-8">
        <h1 className="text-lg font-semibold text-foreground">Users</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {users.length} / 30 seats · click a row to expand queue · dismissed items hidden
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {users.map((user) => (
          <UserQueueCard
            key={user.id}
            userId={user.id}
            email={user.email}
            displayName={user.display_name}
            createdAt={user.created_at}
            interestCount={user.interest_count}
            initialQueue={user.queue}
          />
        ))}
        {users.length === 0 && (
          <p className="text-sm text-muted-foreground">No users yet.</p>
        )}
      </div>
    </main>
  );
}
