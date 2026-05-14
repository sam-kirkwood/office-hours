import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { generatePlan } from "@/lib/plan";
import type { SurveyPayload, CanonicalTopic, CanonicalEdge } from "@/lib/types";

export async function POST(request: Request) {
  try {
    const supabase = await createServerClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

    const body: SurveyPayload = await request.json();

    if (!process.env.SUPABASE_SECRET_KEY) {
      return NextResponse.json({ error: "SUPABASE_SECRET_KEY not set" }, { status: 500 });
    }

    const adminClient = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SECRET_KEY
    );

    const { error: surveyError } = await adminClient.from("surveys").upsert(
      {
        user_id: user.id,
        background_json: body.background,
        topic_states_json: body.topicStates,
        difficulty_curve: body.difficultyCurve,
      },
      { onConflict: "user_id" }
    );
    if (surveyError) {
      return NextResponse.json({ error: surveyError.message }, { status: 500 });
    }

    if (body.extraTopics?.trim()) {
      await adminClient.from("pending_topic_requests").insert({
        requested_by_user_id: user.id,
        raw_topic_text: body.extraTopics.trim(),
      });
    }

    const [{ data: topics, error: topicsError }, { data: edges, error: edgesError }] =
      await Promise.all([
        adminClient.from("canonical_topics").select("*"),
        adminClient.from("canonical_edges").select("*"),
      ]);

    if (topicsError || edgesError || !topics || !edges) {
      return NextResponse.json({ error: "Failed to load curriculum" }, { status: 500 });
    }

    const plannedTopics = generatePlan(
      body.topicStates,
      topics as CanonicalTopic[],
      edges as CanonicalEdge[]
    );

    // Replace any existing pending_review plan, and any active/completed plans
    // (since the user is restarting from a new survey).
    await adminClient.from("user_plans").delete().eq("user_id", user.id);

    const { data: plan, error: planError } = await adminClient
      .from("user_plans")
      .insert({ user_id: user.id, status: "pending_review" })
      .select("id")
      .single();

    if (planError || !plan) {
      return NextResponse.json(
        { error: planError?.message ?? "Failed to create plan" },
        { status: 500 }
      );
    }

    const { error: nodesError } = await adminClient.from("plan_nodes").insert(
      plannedTopics.map((pt, i) => ({
        plan_id: plan.id,
        canonical_topic_id: pt.topicId,
        order_index: i,
        state: pt.initialState === "mastered" ? "mastered" : "pending",
      }))
    );

    if (nodesError) {
      return NextResponse.json({ error: nodesError.message }, { status: 500 });
    }

    return NextResponse.json({ planId: plan.id });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
