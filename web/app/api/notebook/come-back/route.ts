import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// GET /api/notebook/come-back
//
// The "Come back to this" surface (g1): things the user parked for later, which
// previously had no home. Two groups:
//   · bookmarks  — things the user saved with the "Bookmark" action (§A2).
//                  Polymorphic: kind ∈ {node, problem, paper}. Node bookmarks
//                  come from the skill tree (→ "See in skill tree"); problem and
//                  paper bookmarks come from the daily card and carry a backing
//                  'bookmarked' queue item (→ "Queue it now", /api/queue/requeue).
//   · deferred   — queue items they tapped "not ready yet" on (state='deferred').
//
// Deferred items auto-resurface when their prerequisites land (curator's
// /check-deferred); bookmarks never auto-return (the user manages it).

interface ComeBackBookmark {
  // bookmarks.id, so the client can key/optimistically remove.
  bookmark_id: string;
  kind: "node" | "problem" | "paper";
  title: string;
  // node bookmarks → skill-tree link; problem/paper bookmarks → "Queue it now".
  slug: string | null;
  queue_item_id: string | null;
  created_at: string;
}

interface ComeBackDeferred {
  queue_item_id: string;
  kind: string;
  ref_id: string | null;
  title: string;
  node_slug: string | null;
  // Topic node slugs to label the item (a deferred problem has one topic node).
  topics: string[];
  // Problem content so the user can read it before deciding to requeue.
  statement_md: string | null;
  context_md: string | null;
  deferred_at: string | null;
}

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const admin = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  // --- Bookmarks (active = not yet promoted back into the queue) -----------
  const { data: bmRows } = await admin
    .from("bookmarks")
    .select("id, kind, ref_id_or_text, created_at")
    .eq("user_id", user.id)
    .is("promoted_at", null)
    .in("kind", ["node", "problem", "paper"])
    .order("created_at", { ascending: false });

  const rows = (bmRows ?? []) as Array<{
    id: string;
    kind: "node" | "problem" | "paper";
    ref_id_or_text: string;
    created_at: string;
  }>;

  const nodeRefIds = rows.filter((b) => b.kind === "node").map((b) => b.ref_id_or_text);
  const problemRefIds = rows.filter((b) => b.kind === "problem").map((b) => b.ref_id_or_text);
  const paperRefIds = rows.filter((b) => b.kind === "paper").map((b) => b.ref_id_or_text);

  // Resolve node titles + slugs.
  const nodeById: Record<string, { slug: string; title: string }> = {};
  if (nodeRefIds.length > 0) {
    const { data: nodes } = await admin
      .from("nodes")
      .select("id, slug, title")
      .in("id", nodeRefIds);
    for (const n of nodes ?? []) {
      const nn = n as { id: string; slug: string; title: string };
      nodeById[nn.id] = { slug: nn.slug, title: nn.title };
    }
  }

  // Resolve problem titles (fall back to topic node title).
  const problemById: Record<string, { title: string }> = {};
  if (problemRefIds.length > 0) {
    const { data: problems } = await admin
      .from("problems")
      .select("id, title, topic_node_id")
      .in("id", problemRefIds);
    const needNodeIds = (problems ?? [])
      .map((p: { topic_node_id: string | null }) => p.topic_node_id)
      .filter(Boolean) as string[];
    const titleByNode: Record<string, string> = {};
    if (needNodeIds.length > 0) {
      const { data: nodes } = await admin.from("nodes").select("id, title").in("id", needNodeIds);
      for (const n of nodes ?? []) titleByNode[(n as { id: string }).id] = (n as { title: string }).title;
    }
    for (const p of problems ?? []) {
      const pr = p as { id: string; title: string | null; topic_node_id: string | null };
      problemById[pr.id] = {
        title: pr.title ?? (pr.topic_node_id ? titleByNode[pr.topic_node_id] : undefined) ?? "Problem",
      };
    }
  }

  // Resolve paper titles.
  const paperById: Record<string, { title: string }> = {};
  if (paperRefIds.length > 0) {
    const { data: papers } = await admin
      .from("papers")
      .select("id, title")
      .in("id", paperRefIds);
    for (const p of papers ?? []) {
      const pp = p as { id: string; title: string | null };
      paperById[pp.id] = { title: pp.title ?? "Paper" };
    }
  }

  // Backing 'bookmarked' queue items, so problem/paper bookmarks get "Queue it
  // now". A problem queue item references the problem id directly; a paper
  // engagement references the engagement, so map engagement → paper id.
  const queueItemByProblemId: Record<string, string> = {};
  const queueItemByPaperId: Record<string, string> = {};
  if (problemRefIds.length > 0 || paperRefIds.length > 0) {
    const { data: bmQueue } = await admin
      .from("queue_items")
      .select("id, kind, ref_id")
      .eq("user_id", user.id)
      .eq("state", "bookmarked");

    const engRefIds = (bmQueue ?? [])
      .filter((q: { kind: string }) => q.kind === "paper_engagement")
      .map((q: { ref_id: string | null }) => q.ref_id)
      .filter(Boolean) as string[];
    const paperIdByEngId: Record<string, string> = {};
    if (engRefIds.length > 0) {
      const { data: engs } = await admin
        .from("paper_engagements")
        .select("id, paper_id")
        .in("id", engRefIds);
      for (const e of engs ?? []) {
        const ee = e as { id: string; paper_id: string | null };
        if (ee.paper_id) paperIdByEngId[ee.id] = ee.paper_id;
      }
    }

    for (const q of bmQueue ?? []) {
      const qq = q as { id: string; kind: string; ref_id: string | null };
      if (qq.kind === "problem" && qq.ref_id) queueItemByProblemId[qq.ref_id] = qq.id;
      else if (qq.kind === "paper_engagement" && qq.ref_id) {
        const paperId = paperIdByEngId[qq.ref_id];
        if (paperId) queueItemByPaperId[paperId] = qq.id;
      }
    }
  }

  const bookmarks: ComeBackBookmark[] = rows
    .map((b): ComeBackBookmark | null => {
      if (b.kind === "node") {
        const node = nodeById[b.ref_id_or_text];
        if (!node) return null;
        return {
          bookmark_id: b.id,
          kind: "node",
          title: node.title,
          slug: node.slug,
          queue_item_id: null,
          created_at: b.created_at,
        };
      }
      if (b.kind === "problem") {
        const p = problemById[b.ref_id_or_text];
        if (!p) return null;
        return {
          bookmark_id: b.id,
          kind: "problem",
          title: p.title,
          slug: null,
          queue_item_id: queueItemByProblemId[b.ref_id_or_text] ?? null,
          created_at: b.created_at,
        };
      }
      // paper
      const pp = paperById[b.ref_id_or_text];
      if (!pp) return null;
      return {
        bookmark_id: b.id,
        kind: "paper",
        title: pp.title,
        slug: null,
        queue_item_id: queueItemByPaperId[b.ref_id_or_text] ?? null,
        created_at: b.created_at,
      };
    })
    .filter((b): b is ComeBackBookmark => b !== null);

  // --- Deferred queue items ----------------------------------------------
  const { data: deferredRows } = await admin
    .from("queue_items")
    .select("id, kind, ref_id, deferred_at")
    .eq("user_id", user.id)
    .eq("state", "deferred")
    .order("deferred_at", { ascending: false });

  // Defer currently only applies to problems (see /api/problem/[id]/defer),
  // so resolve titles via problems.title → topic node title.
  const problemIds = (deferredRows ?? [])
    .filter((r: { kind: string; ref_id: string | null }) => r.kind === "problem" && r.ref_id)
    .map((r: { ref_id: string }) => r.ref_id);

  const titleByProblemId: Record<string, string> = {};
  const slugByProblemId: Record<string, string> = {};
  const statementByProblemId: Record<string, string | null> = {};
  const contextByProblemId: Record<string, string | null> = {};
  if (problemIds.length > 0) {
    const { data: problems } = await admin
      .from("problems")
      .select("id, title, topic_node_id, statement_md, context_md")
      .in("id", problemIds);
    const nodeIds = (problems ?? [])
      .map((p: { topic_node_id: string | null }) => p.topic_node_id)
      .filter(Boolean) as string[];
    const nodeByIdLocal: Record<string, { title: string; slug: string }> = {};
    if (nodeIds.length > 0) {
      const { data: nodes } = await admin
        .from("nodes")
        .select("id, slug, title")
        .in("id", nodeIds);
      for (const n of nodes ?? []) {
        nodeByIdLocal[(n as { id: string }).id] = {
          title: (n as { title: string }).title,
          slug: (n as { slug: string }).slug,
        };
      }
    }
    for (const p of problems ?? []) {
      const pr = p as {
        id: string;
        title: string | null;
        topic_node_id: string | null;
        statement_md: string | null;
        context_md: string | null;
      };
      const node = pr.topic_node_id ? nodeByIdLocal[pr.topic_node_id] : undefined;
      titleByProblemId[pr.id] = pr.title ?? node?.title ?? "Problem";
      if (node?.slug) slugByProblemId[pr.id] = node.slug;
      statementByProblemId[pr.id] = pr.statement_md ?? null;
      contextByProblemId[pr.id] = pr.context_md ?? null;
    }
  }

  const deferred: ComeBackDeferred[] = (deferredRows ?? []).map(
    (r: { id: string; kind: string; ref_id: string | null; deferred_at: string | null }) => {
      const slug = (r.ref_id && slugByProblemId[r.ref_id]) || null;
      return {
        queue_item_id: r.id,
        kind: r.kind,
        ref_id: r.ref_id,
        title: (r.ref_id && titleByProblemId[r.ref_id]) || "Saved item",
        node_slug: slug,
        topics: slug ? [slug] : [],
        statement_md: (r.ref_id && statementByProblemId[r.ref_id]) || null,
        context_md: (r.ref_id && contextByProblemId[r.ref_id]) || null,
        deferred_at: r.deferred_at,
      };
    },
  );

  return NextResponse.json({ bookmarks, deferred });
}
