import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import {
  generateProblem,
  parseAddInterest,
  proposePapers,
  resolveAddInterest,
  suggestPapers,
} from "@/lib/pythonApi";

// Headless add-interest used when the user has already committed (clicked a
// daily-tab "Add it" button, requested a paper on a topic by typing its name,
// etc.) and we just need to resolve the topic to a node without surfacing
// the dialog. Auto-confirms whatever /parse returned.
async function headlessResolveToNode(args: {
  userId: string;
  rawText: string;
}): Promise<string> {
  const parsed = await parseAddInterest({
    userId: args.userId,
    rawText: args.rawText,
    addedVia: "explicit_request",
  });
  if (parsed.segments.length === 0) {
    throw new Error("Could not parse the topic");
  }
  const seg = parsed.segments[0];
  const resolved = await resolveAddInterest({
    userId: args.userId,
    addedVia: "explicit_request",
    rawText: args.rawText,
    finalIntentText: seg.raw_text_segment || args.rawText,
    intentContext: seg.draft_intent_context || seg.mirror_back_md,
    existingNodeSlug:
      seg.dedup.verdict === "same" ? seg.dedup.matched_node_slug : null,
    relatedNodeSlug:
      seg.dedup.verdict === "related" ? seg.dedup.matched_node_slug : null,
  });
  return resolved.node_id;
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await request.json() as {
    node_id?: string;
    raw_text?: string;
    kind_hint?: "problem" | "paper" | "refresher";
    // §2.7 Case 2 / Case 3 — queue a one-off on this node without making
    // the user permanently interested in it.
    skip_interest_add?: boolean;
  };

  const { node_id, raw_text, kind_hint, skip_interest_add } = body;

  if (!node_id && !raw_text) {
    return NextResponse.json({ error: "node_id or raw_text required" }, { status: 400 });
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  // Resolve node: prefer raw_text (resolves or creates via add-interest),
  // fall back to node_id for the existing skill-tree click path.
  let resolvedNodeId = node_id;

  if (raw_text) {
    resolvedNodeId = await headlessResolveToNode({
      userId: user.id,
      rawText: raw_text,
    });
  } else if (node_id && !skip_interest_add) {
    // Existing path: ensure the node is in user_interests
    const { data: existing } = await adminClient
      .from("user_interests")
      .select("id")
      .eq("user_id", user.id)
      .eq("node_id", node_id)
      .maybeSingle();

    if (!existing) {
      const { data: node } = await adminClient
        .from("nodes")
        .select("title")
        .eq("id", node_id)
        .maybeSingle();
      if (!node) return NextResponse.json({ error: "Node not found" }, { status: 404 });
      await headlessResolveToNode({ userId: user.id, rawText: node.title as string });
    }
  }

  if (!resolvedNodeId) {
    return NextResponse.json({ error: "Could not resolve node" }, { status: 400 });
  }

  const kind = kind_hint ?? "problem";

  // ------------------------------------------------------------------
  // Problem
  // ------------------------------------------------------------------
  if (kind === "problem") {
    const result = await generateProblem({ userId: user.id, nodeId: resolvedNodeId });
    return NextResponse.json({ queue_item_id: result.queue_item_id, kind: "problem" });
  }

  // ------------------------------------------------------------------
  // Paper
  // ------------------------------------------------------------------
  if (kind === "paper") {
    async function pickPendingPaper(): Promise<string | null> {
      const { data: qi } = await adminClient
        .from("queue_items")
        .select("id")
        .eq("user_id", user!.id)
        .eq("kind", "paper_engagement")
        .eq("state", "pending")
        .order("priority_score", { ascending: false })
        .limit(1)
        .maybeSingle();
      return qi?.id ?? null;
    }

    try {
      await suggestPapers({ userId: user.id });
    } catch {
      // best-effort; continue to check for any available paper
    }

    let qiId = await pickPendingPaper();

    // Pool miss → expand via /propose-papers, then re-run /suggest-papers.
    // Phase 10-rev §Step 4 #5. The user should never see "check back soon"
    // on a topic the system knows about. proposePapers is idempotent
    // (dedups by title/arxiv_id/doi) so the retry is cheap.
    if (!qiId) {
      try {
        await proposePapers({ userId: user.id });
        await suggestPapers({ userId: user.id });
      } catch {
        // best-effort; fall through to the "added — appearing shortly" message
      }
      qiId = await pickPendingPaper();
    }

    if (qiId) {
      return NextResponse.json({ queue_item_id: qiId, kind: "paper_engagement" });
    }
    return NextResponse.json({
      queue_item_id: null,
      kind: "paper_engagement",
      message: "Adding a paper to your queue — it'll appear shortly.",
    });
  }

  // ------------------------------------------------------------------
  // Refresher
  // ------------------------------------------------------------------
  if (kind === "refresher") {
    // Look for an already-due refresher schedule row for this user
    const { data: schedule } = await adminClient
      .from("refresher_schedule")
      .select("id, subject_kind, subject_ref_id")
      .eq("user_id", user.id)
      .is("surfaced_at", null)
      .lte("due_at", new Date().toISOString())
      .limit(1)
      .maybeSingle();

    let scheduleId: string | null = schedule?.id ?? null;

    if (!scheduleId) {
      // On-demand: prefer a notebook entry that matches the requested node (via
      // topic_node_slugs), fall back to the most recent entry if no match.
      let entry: { ref_id: string; entry_kind: string } | null = null;

      if (resolvedNodeId) {
        const { data: node } = await adminClient
          .from("nodes")
          .select("slug")
          .eq("id", resolvedNodeId)
          .maybeSingle();
        if (node?.slug) {
          const { data: topicEntry } = await adminClient
            .from("notebook_entries")
            .select("ref_id, entry_kind")
            .eq("user_id", user.id)
            .contains("topic_node_slugs", [node.slug])
            .order("created_at", { ascending: false })
            .limit(1)
            .maybeSingle();
          entry = topicEntry ?? null;
        }
      }

      if (!entry) {
        const { data: recentEntry } = await adminClient
          .from("notebook_entries")
          .select("ref_id, entry_kind")
          .eq("user_id", user.id)
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();
        entry = recentEntry ?? null;
      }

      if (!entry) {
        return NextResponse.json({
          queue_item_id: null,
          kind: "refresher",
          message: "No content to refresh yet — keep working!",
        });
      }

      const subjectKind = entry.entry_kind === "problem_attempt" ? "attempt" : "engagement";
      const { data: newSched } = await adminClient
        .from("refresher_schedule")
        .insert({
          user_id: user.id,
          subject_kind: subjectKind,
          subject_ref_id: entry.ref_id,
          due_at: new Date().toISOString(),
        })
        .select("id")
        .single();

      scheduleId = newSched?.id ?? null;
    }

    if (!scheduleId) {
      return NextResponse.json({
        queue_item_id: null,
        kind: "refresher",
        message: "Could not create refresher. Try again later.",
      });
    }

    const { data: qi } = await adminClient
      .from("queue_items")
      .insert({
        user_id: user.id,
        kind: "refresher",
        ref_id: scheduleId,
        state: "pending",
        priority_score: 0.9,
        added_reason: "Revisit something you've worked on.",
        time_estimate_minutes_low: 10,
        time_estimate_minutes_high: 30,
      })
      .select("id")
      .single();

    // Mark due schedules as surfaced so they aren't re-enqueued by future runs.
    if (schedule) {
      await adminClient
        .from("refresher_schedule")
        .update({ surfaced_at: new Date().toISOString() })
        .eq("id", scheduleId);
    }

    return NextResponse.json({
      queue_item_id: qi?.id ?? null,
      kind: "refresher",
      message: qi?.id ? null : "Refresher added to your queue.",
    });
  }

  return NextResponse.json({ error: "Unknown kind" }, { status: 400 });
}
