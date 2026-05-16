import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: queueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: queueItem } = await adminClient
    .from("queue_items")
    .select("id, ref_id")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!queueItem) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { data: problem } = await adminClient
    .from("problems")
    .select("id, topic_node_id")
    .eq("id", queueItem.ref_id)
    .maybeSingle();

  await adminClient.from("attempts").insert({
    user_id: user.id,
    problem_id: queueItem.ref_id,
    queue_item_id: queueItemId,
    marked_refreshed: true,
    hint_levels_used: [],
    parse_status: null,
    raw_image_paths: [],
  });

  await adminClient
    .from("queue_items")
    .update({ state: "done", updated_at: new Date().toISOString() })
    .eq("id", queueItemId);

  if (problem?.topic_node_id) {
    const { data: existing } = await adminClient
      .from("user_node_states")
      .select("state, engagement_count")
      .eq("user_id", user.id)
      .eq("node_id", problem.topic_node_id)
      .maybeSingle();

    const newCount = (existing?.engagement_count ?? 0) + 1;
    const cur = existing?.state ?? "unseen";
    const newState = cur === "unseen" || cur === "active" ? "comfortable" : cur;

    await adminClient
      .from("user_node_states")
      .upsert(
        { user_id: user.id, node_id: problem.topic_node_id, engagement_count: newCount, state: newState },
        { onConflict: "user_id,node_id" },
      );
  }

  return NextResponse.json({ ok: true });
}
