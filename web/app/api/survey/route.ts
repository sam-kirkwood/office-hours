import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { addInterest, updateQueue } from "@/lib/pythonApi";
import type { SurveyV2Payload, NodeRating } from "@/lib/types";

export async function POST(request: Request) {
  try {
    const supabase = await createServerClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

    const body: SurveyV2Payload = await request.json();
    const { free_text_intent, node_ratings, comfort_responses, mode_balance } = body;

    if (!process.env.SUPABASE_SECRET_KEY) {
      return NextResponse.json({ error: "SUPABASE_SECRET_KEY not set" }, { status: 500 });
    }

    const adminClient = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SECRET_KEY,
    );

    // 1. Upsert surveys row.
    const { error: surveyError } = await adminClient.from("surveys").upsert(
      {
        user_id: user.id,
        free_text_intent,
        node_ratings_json: node_ratings,
        comfort_responses_json: comfort_responses ?? {},
        mode_balance: mode_balance ?? 0.5,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "user_id" },
    );
    if (surveyError) {
      return NextResponse.json({ error: surveyError.message }, { status: 500 });
    }

    // 2. Load nodes to resolve slugs → IDs for user_node_states writes.
    const { data: nodes, error: nodesError } = await adminClient
      .from("nodes")
      .select("id, slug, title");
    if (nodesError) {
      return NextResponse.json({ error: nodesError.message }, { status: 500 });
    }
    const nodeBySlug = Object.fromEntries((nodes ?? []).map((n) => [n.slug, n]));

    // 3. For each "interested" node: call /add-interest (writes user_interests).
    const interestedSlugs = Object.entries(node_ratings ?? {})
      .filter(([, rating]: [string, NodeRating]) => rating === "interested")
      .map(([slug]) => slug);

    for (const slug of interestedSlugs) {
      const node = nodeBySlug[slug];
      if (!node) continue;
      try {
        await addInterest({ userId: user.id, rawText: node.title, addedVia: "survey" });
      } catch (err) {
        console.error(`addInterest failed for slug=${slug}:`, err);
      }
    }

    // 4. If free-text intent is non-empty: call /add-interest for the whole string.
    if (free_text_intent?.trim()) {
      try {
        await addInterest({
          userId: user.id,
          rawText: free_text_intent.trim(),
          addedVia: "survey",
        });
      } catch (err) {
        console.error("addInterest failed for free_text_intent:", err);
      }
    }

    // 5. Seed user_node_states for "comfortable" and "refresh" nodes.
    const stateRows = Object.entries(node_ratings ?? {})
      .filter(([, rating]: [string, NodeRating]) => rating === "comfortable" || rating === "refresh")
      .flatMap(([slug, rating]: [string, NodeRating]) => {
        const node = nodeBySlug[slug];
        if (!node) return [];
        return [
          {
            user_id: user.id,
            node_id: node.id,
            state: rating === "comfortable" ? "comfortable" : "active",
          },
        ];
      });

    if (stateRows.length > 0) {
      const { error: stateError } = await adminClient
        .from("user_node_states")
        .upsert(stateRows, { onConflict: "user_id,node_id" });
      if (stateError) {
        console.error("user_node_states upsert failed:", stateError);
      }
    }

    // 6. Seed placeholder queue items so /daily has cards to show.
    // Fetch the user's interests (includes nodes matched by dedup and newly-created
    // ones from free-text — addInterest has now written all of them).
    // Real queue population happens in Phase 7-rev via update_queue.
    try {
      const { data: interests } = await adminClient
        .from("user_interests")
        .select("node_id")
        .eq("user_id", user.id);

      if (interests && interests.length > 0) {
        const nodeIds = interests.map((i: { node_id: string }) => i.node_id);
        const { data: interestNodes } = await adminClient
          .from("nodes")
          .select("id, title")
          .in("id", nodeIds);
        const titleById: Record<string, string> = Object.fromEntries(
          (interestNodes ?? []).map((n: { id: string; title: string }) => [n.id, n.title]),
        );
        await adminClient.from("queue_items").insert(
          interests.map((i: { node_id: string }) => ({
            user_id: user.id,
            kind: "suggested_interest",
            ref_id: i.node_id,
            added_reason: `Based on your interest in ${titleById[i.node_id] ?? "this topic"}`,
            priority_score: 0.5,
          })),
        );
      }
    } catch (err) {
      console.error("queue seeding failed:", err);
    }

    // 7. Initialise the queue (stub — real logic in Phase 7-rev).
    try {
      await updateQueue({ userId: user.id });
    } catch (err) {
      console.error("updateQueue failed:", err);
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
