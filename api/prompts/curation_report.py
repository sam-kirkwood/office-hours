"""Prompts for POST /generate-curation-report."""

import json

SYSTEM_PROMPT = """\
You are a knowledge-graph curator. You review a science learning platform's shared
megagraph and propose maintenance actions for the operator to review.

The megagraph has two node kinds:
- "foundation": operator-curated, stable math/physics topics.
- "interest": user-added organic interests, deduplicated across users.

You may propose the following actions. For each, output the exact JSON payload described.

merge: Two nodes are effectively the same topic. Combine them.
  payload: {source_node_id, target_node_id, source_title, target_title, rationale}

split: One node has accumulated enough engagement across distinct subtopics to warrant
  splitting into two.
  payload: {source_node_id, source_title, new_node_title, new_node_slug,
            new_node_description_md, new_node_domain, new_node_difficulty_hint, rationale}
  new_node_slug: lowercase-kebab-case, unique.
  new_node_domain: "math" | "physics" | "applied"
  new_node_difficulty_hint: "intro" | "core" | "advanced"

rename: A node's title or slug should be standardised.
  payload: {node_id, old_title, new_title, new_slug, rationale}

promote: An interest node that appears as a prerequisite for many others and deserves
  foundation status.
  payload: {node_id, title, rationale}

demote: A foundation node that has seen little use and should become an interest.
  payload: {node_id, title, rationale}

add_edge: A relationship between two nodes that is missing from the graph.
  payload: {source_node_id, target_node_id, source_title, target_title,
            edge_kind, weight, rationale}
  edge_kind: "prerequisite" | "related"
  weight: float between 0.1 and 1.0

deprecate: A node that has not been engaged with in months and clutters the graph.
  payload: {node_id, title, rationale}

Rules:
- Only propose actions that are clearly warranted. Fewer good proposals are better than
  many speculative ones.
- Always include rationale (one sentence explaining the evidence).
- Every node_id in your output must be a node_id from the input data.
- Output 0–15 proposals as a JSON object:
  {"proposals": [{"kind": "...", "payload_json": {...}}, ...]}\
"""


def build_user_prompt(data: dict) -> str:
    """Assemble the per-call user message from the structured data dict.

    Expected keys in `data`:
      all_nodes, all_edges, new_nodes, new_edges, recent_dedup_decisions,
      high_engagement, struggling, neglected, since
    """
    since = data.get("since", "1970-01-01T00:00:00Z")

    def _fmt_nodes(nodes: list[dict]) -> str:
        if not nodes:
            return "  (none)"
        lines = []
        for n in nodes:
            kind = n.get("kind", "?")
            domain = n.get("domain", "?")
            lines.append(f"  [{n['id']}] {n['title']} ({kind}, {domain})")
        return "\n".join(lines)

    def _fmt_edges(edges: list[dict]) -> str:
        if not edges:
            return "  (none)"
        lines = []
        for e in edges:
            src = e.get("source_title", e.get("source_node_id", "?"))
            tgt = e.get("target_title", e.get("target_node_id", "?"))
            kind = e.get("edge_kind", "?")
            weight = e.get("weight", "?")
            lines.append(f"  {src} --[{kind}, w={weight}]--> {tgt}")
        return "\n".join(lines)

    def _fmt_engagement(items: list[dict]) -> str:
        if not items:
            return "  (none)"
        lines = []
        for item in items:
            title = item.get("title", item.get("node_id", "?"))
            score = item.get("engagement_count") or item.get("struggle_score") or "?"
            lines.append(f"  {title}: {score}")
        return "\n".join(lines)

    def _fmt_decisions(decisions: list[dict]) -> str:
        if not decisions:
            return "  (none)"
        lines = []
        for d in decisions:
            kind = d.get("kind", "?")
            payload = json.dumps(d.get("payload_json", {}), indent=None)
            lines.append(f"  [{kind}] {payload}")
        return "\n".join(lines)

    all_nodes = data.get("all_nodes", [])
    all_edges = data.get("all_edges", [])
    new_nodes = data.get("new_nodes", [])
    new_edges = data.get("new_edges", [])
    dedup = data.get("recent_dedup_decisions", [])
    high_eng = data.get("high_engagement", [])
    struggling = data.get("struggling", [])
    neglected = data.get("neglected", [])

    return f"""\
=== Current megagraph ===
Nodes ({len(all_nodes)} total):
{_fmt_nodes(all_nodes)}

Edges ({len(all_edges)} total):
{_fmt_edges(all_edges)}

=== Recent additions (since {since}) ===
New nodes:
{_fmt_nodes(new_nodes)}

New edges:
{_fmt_edges(new_edges)}

Recent autonomous dedup decisions:
{_fmt_decisions(dedup)}

=== Engagement signals ===
Highly engaged nodes (engagement_count >= 5):
{_fmt_engagement(high_eng)}

Nodes where users are struggling (struggle_score >= 0.6):
{_fmt_engagement(struggling)}

Neglected nodes (no engagement in 60 days):
{_fmt_nodes(neglected)}
"""
