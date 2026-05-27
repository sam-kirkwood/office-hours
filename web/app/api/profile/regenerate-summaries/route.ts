import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient } from "@/lib/surveyState";
import { rewriteIntentSummaries, type RewriteSummaryItem } from "@/lib/pythonApi";

// POST /api/profile/regenerate-summaries
// Backfill: rewrite the user's tag-soup intent_context values into natural
// prose summaries. One Haiku batch call. The result is written back to
// user_interests so subsequent reads (profile page, problem generator) get
// the cleaner text.
//
// Idempotent — running it twice is safe (Haiku will mostly leave already-
// clean prose alone). No body required.

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const admin = getAdminClient();

  const { data: interestRows, error } = await admin
    .from("user_interests")
    .select(
      "id, intent_context, nodes(title, description_md, subtopics_json)",
    )
    .eq("user_id", user.id);
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  type NodeShape = {
    title: string;
    description_md: string | null;
    subtopics_json: unknown;
  };
  type Row = {
    id: string;
    intent_context: string;
    nodes: NodeShape | NodeShape[] | null;
  };

  // subtopics_json: bare strings (interest nodes) or {slug,title} (foundation).
  function subtopicTitles(raw: unknown): string[] {
    if (!Array.isArray(raw)) return [];
    const out: string[] = [];
    for (const entry of raw) {
      if (typeof entry === "string") out.push(entry);
      else if (entry && typeof entry === "object") {
        const e = entry as { title?: unknown; name?: unknown; slug?: unknown };
        const t = e.title ?? e.name ?? e.slug;
        if (typeof t === "string") out.push(t);
      }
    }
    return out;
  }

  const items: RewriteSummaryItem[] = [];
  for (const r of (interestRows as Row[] | null) ?? []) {
    const node = Array.isArray(r.nodes) ? r.nodes[0] : r.nodes;
    if (!node) continue;
    items.push({
      user_interest_id: r.id,
      node_title: node.title,
      node_description_md: node.description_md ?? null,
      subtopics: subtopicTitles(node.subtopics_json),
      current_context: r.intent_context ?? "",
    });
  }

  if (items.length === 0) {
    return NextResponse.json({ rewritten: 0 });
  }

  let summaries: Array<{ user_interest_id: string; summary: string }>;
  try {
    const result = await rewriteIntentSummaries({
      userId: user.id,
      items,
    });
    summaries = result.summaries;
  } catch (err) {
    const message = err instanceof Error ? err.message : "Rewrite failed";
    return NextResponse.json({ error: message }, { status: 502 });
  }

  // Write back one row at a time. Volumes are tiny (<= ~30 per user).
  let rewritten = 0;
  for (const s of summaries) {
    if (!s.summary?.trim()) continue;
    const { error: updErr } = await admin
      .from("user_interests")
      .update({ intent_context: s.summary.trim() })
      .eq("id", s.user_interest_id)
      .eq("user_id", user.id);
    if (updErr) {
      return NextResponse.json({ error: updErr.message }, { status: 500 });
    }
    rewritten += 1;
  }

  return NextResponse.json({ rewritten });
}
