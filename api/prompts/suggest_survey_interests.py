"""Prompt for /survey/suggest-interests (Stage 3 of the onboarding survey).

Haiku reranks a small heuristic shortlist of interest-kind nodes into the
final 6–10 tiles shown on the Stage 3 page, with a short "why suggested"
line per tile (survey-and-difficulty-design.md §1.4.1).

The heuristic shortlist (computed in the route) already restricts to nodes
whose domain matches the user's Stage 1 chips and gives priority to nodes
with prerequisite edges into the foundations the user marked refresh in
Stage 2, plus a small boost for sub-area label keyword overlap. Haiku's job
is the final selection + one-line rationale that the user actually sees.
"""

from __future__ import annotations


def build_system_prompt() -> str:
    return (
        "You are helping personalise the onboarding for a private science "
        "tutor used by working professionals. The user has just described "
        "their background by picking broad areas, sub-areas within each, "
        "and a relationship card per area. You will be given a small "
        "shortlist of interest-kind topics from a shared knowledge graph; "
        "your job is to choose between 6 and 10 of them to show, in "
        "priority order, with a one-line 'why we're suggesting this' for "
        "each.\n"
        "\n"
        "Return ONLY a JSON object of this exact shape:\n"
        '{"suggestions": [\n'
        '  {"slug": "kebab-slug-from-shortlist", "why_suggested_md": "string"}\n'
        "]}\n"
        "\n"
        "Rules:\n"
        "- slug MUST appear in the shortlist provided. Do not invent slugs.\n"
        "- Pick at least 6 and at most 10 entries. Order them so the "
        "  strongest matches to the user's stated background come first.\n"
        "- Use the sub-area picks as the primary signal. A user who ticks "
        "  'condensed matter' under Physics should see solid-state-adjacent "
        "  topics ahead of, say, particle physics. A user with Chemistry "
        "  background ticked should see materials-physics-adjacent topics "
        "  boosted even though we don't run chem problems directly.\n"
        "- why_suggested_md is ONE sentence, at most 110 characters, "
        "  written like a knowledgeable peer (not a marketing line). Name "
        "  the connection where you can — e.g. 'Builds on the condensed "
        "  matter angle you flagged.' or 'A natural follow-on if you're "
        "  rebuilding ODEs.' Plain prose, no labels, no exclamation marks.\n"
        "- If a relationship card on a domain leans 'curious' or 'follow "
        "  this field', favour conceptually accessible entries for that "
        "  domain. 'Reconnecting' or 'encounter at work' → favour topics "
        "  that re-engage existing fluency.\n"
        "- Do not condescend, do not assume the user is a beginner."
    )


def build_user_prompt(
    *,
    domains: list[dict],
    short_text: str,
    marked_foundation_titles: list[str],
    shortlist: list[dict],
) -> str:
    if domains:
        domain_lines = []
        for d in domains:
            sub_str = (
                ", ".join(d.get("subarea_labels") or []) or "(no sub-areas picked)"
            )
            rel_str = d.get("relationship_label") or "(no relationship card)"
            domain_lines.append(
                f"- {d.get('label', d.get('key', '?'))}: sub-areas {sub_str}; relationship: {rel_str}"
            )
        domains_block = "User's background by area:\n" + "\n".join(domain_lines)
    else:
        domains_block = "User's background by area: (none picked)"

    text_block = short_text.strip() if short_text and short_text.strip() else "(none)"
    marked_block = (
        ", ".join(marked_foundation_titles) if marked_foundation_titles else "(none)"
    )
    shortlist_lines = "\n".join(
        f'- slug="{c["slug"]}" title="{c["title"]}" '
        f'desc="{(c.get("description_md") or "")[:140]}" '
        f'prereq_overlap={c.get("prereq_overlap_count", 0)} '
        f'subarea_overlap={c.get("subarea_overlap_count", 0)}'
        for c in shortlist
    )
    return (
        f"{domains_block}\n"
        f"User's optional background note: \"{text_block}\"\n"
        f"Foundations the user flagged for refresh: {marked_block}\n"
        f"\n"
        f"Shortlist of interest-kind nodes (pick 6–10 of these):\n{shortlist_lines}"
    )
