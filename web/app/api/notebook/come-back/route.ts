import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

// GET /api/notebook/come-back
//
// The "Come back to this" surface (g1): things the user parked for later, which
// previously had no home. Two groups:
//   · bookmarks  — nodes the user bookmarked from the skill tree
//   · deferred   — queue items they tapped "not ready yet" on (state='deferred')
//
// Deferred items auto-resurface when their prerequisites land (curator's
// /check-deferred), but until then they're invisible; this gives them a place
// to live and a manual "queue it now" path (see /api/queue/resume).

interface ComeBackBookmark {
  node_id: string;
  slug: string;
  title: string;
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

  // --- Bookmarks (kind='node') -------------------------------------------
  const { data: bmRows } = await admin
    .from("bookmarks")
    .select("ref_id_or_text, created_at")
    .eq("user_id", user.id)
    .eq("kind", "node")
    .order("created_at", { ascending: false });

  const bookmarkNodeIds = (bmRows ?? []).map(
    (b: { ref_id_or_text: string }) => b.ref_id_or_text,
  );

  let bookmarks: ComeBackBookmark[] = [];
  if (bookmarkNodeIds.length > 0) {
    const { data: nodes } = await admin
      .from("nodes")
      .select("id, slug, title")
      .in("id", bookmarkNodeIds);
    const nodeById = Object.fromEntries(
      (nodes ?? []).map((n: { id: string; slug: string; title: string }) => [n.id, n]),
    );
    bookmarks = (bmRows ?? [])
      .map((b: { ref_id_or_text: string; created_at: string }) => {
        const node = nodeById[b.ref_id_or_text];
        return node
          ? { node_id: node.id, slug: node.slug, title: node.title, created_at: b.created_at }
          : null;
      })
      .filter((b): b is ComeBackBookmark => b !== null);
  }

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
    const nodeById: Record<string, { title: string; slug: string }> = {};
    if (nodeIds.length > 0) {
      const { data: nodes } = await admin
        .from("nodes")
        .select("id, slug, title")
        .in("id", nodeIds);
      for (const n of nodes ?? []) {
        nodeById[(n as { id: string }).id] = {
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
      const node = pr.topic_node_id ? nodeById[pr.topic_node_id] : undefined;
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
