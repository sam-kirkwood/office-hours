import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import {
  createRefresher,
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
    // Source queue item id when this request was triggered from inside
    // another surface (e.g. an orienting concept click in a paper). Used
    // by the resulting concept_review / refresher reading view to render
    // a back-link to the source.
    parent_queue_item_id?: string;
  };

  const { node_id, raw_text, kind_hint, skip_interest_add, parent_queue_item_id } = body;

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
  // A refresher is resolved to concrete content at creation time by the Python
  // /create-refresher endpoint, which also decides refresher-vs-groundwork: a
  // node the user has engaged (or marked) resolves to a via_refresher item; a
  // node they've never met resolves to a plain orientation read. We only decide
  // *what to point at* here:
  //   1. a due refresher_schedule (revisit a specific prior attempt/paper),
  //   2. a targeted node, or
  //   3. the most recent notebook entry (a generic "any refresher" request).
  if (kind === "refresher") {
    const now = new Date().toISOString();

    // refId is what we hand to /create-refresher: a refresher_schedule.id or a
    // nodes.id. scheduleToSurface is set when refId is a schedule we must mark
    // surfaced on success so it isn't re-enqueued.
    let refId: string | null = null;
    let scheduleToSurface: string | null = null;

    // 1. Already-due schedule.
    const { data: schedule } = await adminClient
      .from("refresher_schedule")
      .select("id")
      .eq("user_id", user.id)
      .is("surfaced_at", null)
      .lte("due_at", now)
      .limit(1)
      .maybeSingle();
    if (schedule?.id) {
      refId = schedule.id;
      scheduleToSurface = schedule.id;
    }

    // 2. Targeted node → resolve on it (Python downgrades to a groundwork read
    //    if the user has no basis to refresh it). Else 3. fall back to the most
    //    recent notebook entry (a generic "any refresher" request).
    if (!refId) {
      if (resolvedNodeId) {
        refId = resolvedNodeId;
      } else {
        const { data: recentEntry } = await adminClient
          .from("notebook_entries")
          .select("ref_id, entry_kind")
          .eq("user_id", user.id)
          .order("created_at", { ascending: false })
          .limit(1)
          .maybeSingle();
        if (!recentEntry) {
          return NextResponse.json({
            queue_item_id: null,
            kind: "refresher",
            message: "No content to refresh yet — keep working!",
          });
        }
        const subjectKind =
          recentEntry.entry_kind === "problem_attempt" ? "attempt" : "engagement";
        const { data: newSched } = await adminClient
          .from("refresher_schedule")
          .insert({
            user_id: user.id,
            subject_kind: subjectKind,
            subject_ref_id: recentEntry.ref_id,
            due_at: now,
          })
          .select("id")
          .single();
        refId = newSched?.id ?? null;
        scheduleToSurface = newSched?.id ?? null;
      }
    }

    if (!refId) {
      return NextResponse.json({
        queue_item_id: null,
        kind: "refresher",
        message: "Could not create refresher. Try again later.",
      });
    }

    try {
      const resolved = await createRefresher({
        userId: user.id,
        refId,
        reason: "Revisit something you've worked on.",
        priorityScore: 0.9,
        parentQueueItemId: parent_queue_item_id ?? null,
      });
      if (scheduleToSurface) {
        await adminClient
          .from("refresher_schedule")
          .update({ surfaced_at: now })
          .eq("id", scheduleToSurface);
      }
      return NextResponse.json({
        queue_item_id: resolved.queue_item_id,
        kind: resolved.kind,
      });
    } catch {
      return NextResponse.json({
        queue_item_id: null,
        kind: "refresher",
        message: "Could not create refresher. Try again later.",
      });
    }
  }

  return NextResponse.json({ error: "Unknown kind" }, { status: 400 });
}
