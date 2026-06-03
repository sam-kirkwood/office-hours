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

  const { data: qi } = await adminClient
    .from("queue_items")
    .select("id, kind, ref_id, state")
    .eq("id", queueItemId)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!qi) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (qi.kind !== "concept_review") {
    return NextResponse.json(
      { error: "queue_item is not a concept_review" },
      { status: 400 },
    );
  }
  if (qi.state === "done" || qi.state === "dismissed") {
    return NextResponse.json({ ok: true, already_done: true });
  }

  await adminClient
    .from("queue_items")
    .update({ state: "done", updated_at: new Date().toISOString() })
    .eq("id", queueItemId);

  // Persist to notebook so the user can revisit the brief later. The entry's
  // ref_id points at the node so /notebook/[id] can fetch the cached brief
  // from node_concept_briefs. Skip silently if a row already exists for this
  // (user, node) — repeated concept reviews on the same node shouldn't
  // accumulate notebook entries.
  if (qi.ref_id) {
    const { data: node } = await adminClient
      .from("nodes")
      .select("title, slug")
      .eq("id", qi.ref_id)
      .maybeSingle();
    if (node?.title && node?.slug) {
      const { data: existing } = await adminClient
        .from("notebook_entries")
        .select("id")
        .eq("user_id", user.id)
        .eq("entry_kind", "concept_review")
        .eq("ref_id", qi.ref_id)
        .maybeSingle();
      if (!existing) {
        await adminClient.from("notebook_entries").insert({
          user_id: user.id,
          entry_kind: "concept_review",
          ref_id: qi.ref_id,
          title: `${node.title} — Concept`,
          topic_node_slugs: [node.slug],
        });
      }
    }
  }

  return NextResponse.json({ ok: true });
}
