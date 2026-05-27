import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getAdminClient } from "@/lib/surveyState";
import ProfileView, {
  type ProfileInterest,
  type ProfileFoundation,
  type QueuedItem,
} from "@/components/profile/ProfileView";

// /profile — the home for mode balance, high-level feedback, interest
// management, and a read-only view of foundation node states
// (survey-and-difficulty-design.md §6).
//
// Each interest can be expanded inline to show what's currently queued under
// it (active problem queue items joined by problems.topic_node_id) and the
// user's engagement count for that node.

export default async function ProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();

  const [
    { data: surveyRow },
    { data: prefRows },
    { data: interestRows },
    { data: foundationRows },
    { data: stateRows },
  ] = await Promise.all([
    admin
      .from("surveys")
      .select("mode_balance")
      .eq("user_id", user.id)
      .maybeSingle(),
    admin
      .from("user_preferences")
      .select("key, value")
      .eq("user_id", user.id),
    admin
      .from("user_interests")
      .select("id, node_id, intent_context, nodes(id, slug, title)")
      .eq("user_id", user.id),
    admin
      .from("nodes")
      .select("id, slug, title, domain")
      .eq("kind", "foundation"),
    admin
      .from("user_node_states")
      .select("node_id, state, engagement_count")
      .eq("user_id", user.id),
  ]);

  const modeBalance = (surveyRow?.mode_balance as number | undefined) ?? 0.5;

  const feedback: Record<string, boolean> = {};
  for (const row of prefRows ?? []) {
    const r = row as { key: string; value: string };
    if (r.value === "true") feedback[r.key] = true;
  }

  const stateByNodeId = new Map<string, { state: string; engagement_count: number }>();
  for (const row of stateRows ?? []) {
    const r = row as { node_id: string; state: string; engagement_count: number };
    stateByNodeId.set(r.node_id, { state: r.state, engagement_count: r.engagement_count });
  }

  const interestsBase = (interestRows ?? [])
    .map((row) => {
      const r = row as unknown as {
        id: string;
        node_id: string;
        intent_context: string;
        nodes:
          | { id: string; slug: string; title: string }
          | { id: string; slug: string; title: string }[]
          | null;
      };
      const node = Array.isArray(r.nodes) ? r.nodes[0] : r.nodes;
      if (!node) return null;
      return {
        user_interest_id: r.id,
        node_id: r.node_id,
        node_slug: node.slug,
        node_title: node.title,
        intent_context: r.intent_context ?? "",
      };
    })
    .filter((x): x is Omit<ProfileInterest, "engagement_count" | "queued"> => x !== null);

  // Pull active problem queue items linked to any of this user's interests.
  // We fetch the queue rows + problems in one round-trip and group client-side.
  const interestNodeIds = interestsBase.map((i) => i.node_id);
  const queuedByNodeId = new Map<string, QueuedItem[]>();

  if (interestNodeIds.length > 0) {
    const { data: queuedRows } = await admin
      .from("queue_items")
      .select("id, kind, ref_id, state, added_reason, problems!inner(id, title, topic_node_id)")
      .eq("user_id", user.id)
      .eq("kind", "problem")
      .in("state", ["pending", "surfaced", "in_progress"])
      .in(
        "problems.topic_node_id",
        interestNodeIds,
      );

    for (const row of queuedRows ?? []) {
      const r = row as unknown as {
        id: string;
        kind: string;
        ref_id: string | null;
        state: string;
        added_reason: string | null;
        problems:
          | { id: string; title: string | null; topic_node_id: string }
          | { id: string; title: string | null; topic_node_id: string }[]
          | null;
      };
      const problem = Array.isArray(r.problems) ? r.problems[0] : r.problems;
      if (!problem) continue;
      const item: QueuedItem = {
        queue_item_id: r.id,
        kind: r.kind,
        state: r.state,
        title: problem.title ?? "Untitled problem",
        added_reason: r.added_reason,
      };
      const list = queuedByNodeId.get(problem.topic_node_id) ?? [];
      list.push(item);
      queuedByNodeId.set(problem.topic_node_id, list);
    }
  }

  const interests: ProfileInterest[] = interestsBase.map((i) => ({
    ...i,
    engagement_count: stateByNodeId.get(i.node_id)?.engagement_count ?? 0,
    queued: queuedByNodeId.get(i.node_id) ?? [],
  }));

  const foundations: ProfileFoundation[] = (foundationRows ?? [])
    .map((row) => {
      const r = row as { id: string; slug: string; title: string; domain: string };
      const s = stateByNodeId.get(r.id);
      return {
        node_id: r.id,
        node_slug: r.slug,
        node_title: r.title,
        domain: r.domain,
        state: (s?.state as ProfileFoundation["state"]) ?? "unseen",
        engagement_count: s?.engagement_count ?? 0,
      };
    })
    .sort((a, b) =>
      a.domain === b.domain
        ? a.node_title.localeCompare(b.node_title)
        : a.domain.localeCompare(b.domain),
    );

  return (
    <main className="min-h-screen bg-background">
      <ProfileView
        modeBalance={modeBalance}
        feedback={feedback}
        interests={interests}
        foundations={foundations}
      />
    </main>
  );
}
