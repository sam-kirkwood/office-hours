import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { generatePlan } from "@/lib/plan";
import type { CanonicalTopic, CanonicalEdge, TopicStateMap } from "@/lib/types";

export async function POST(request: Request) {
  try {
    const supabase = await createServerClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

    const { notes } = await request.json();

    if (!process.env.SUPABASE_SECRET_KEY) {
      return NextResponse.json({ error: "SUPABASE_SECRET_KEY not set" }, { status: 500 });
    }

    const adminClient = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SECRET_KEY
    );

    const { data: plan } = await adminClient
      .from("user_plans")
      .select("id")
      .eq("user_id", user.id)
      .eq("status", "pending_review")
      .maybeSingle();

    if (!plan) {
      return NextResponse.json({ error: "No pending plan found" }, { status: 404 });
    }

    await adminClient
      .from("user_plans")
      .update({ adjustment_notes: notes })
      .eq("id", plan.id);

    const { data: survey } = await adminClient
      .from("surveys")
      .select("topic_states_json")
      .eq("user_id", user.id)
      .maybeSingle();

    if (!survey) {
      return NextResponse.json({ error: "Survey not found" }, { status: 404 });
    }

    const [{ data: topics }, { data: edges }] = await Promise.all([
      adminClient.from("canonical_topics").select("*"),
      adminClient.from("canonical_edges").select("*"),
    ]);

    if (!topics || !edges) {
      return NextResponse.json({ error: "Failed to load curriculum" }, { status: 500 });
    }

    const plannedTopics = generatePlan(
      (survey.topic_states_json ?? {}) as TopicStateMap,
      topics as CanonicalTopic[],
      edges as CanonicalEdge[]
    );

    await adminClient.from("plan_nodes").delete().eq("plan_id", plan.id);

    await adminClient.from("plan_nodes").insert(
      plannedTopics.map((pt, i) => ({
        plan_id: plan.id,
        canonical_topic_id: pt.topicId,
        order_index: i,
        state: pt.initialState === "mastered" ? "mastered" : "pending",
      }))
    );

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
