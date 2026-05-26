"""Prompt for /survey/suggest-interests (Stage 3 of the onboarding survey).

Haiku reranks a small heuristic shortlist of interest-kind nodes into the
final 6–10 tiles shown on the Stage 3 page, with a short "why suggested"
line per tile (survey-and-difficulty-design.md §1.4.1).

The heuristic shortlist (computed in the route) already restricts to nodes
that domain-match the user's Stage 1 chips and have prerequisite edges into
the foundations they marked refresh in Stage 2. Haiku's job is the final
selection + one-line rationale that the user actually sees.
"""

from __future__ import annotations


def build_system_prompt() -> str:
    return (
        "You are helping personalise the onboarding for a private science "
        "tutor used by working professionals. The user has just told us "
        "which broad domains they care about and which foundation topics "
        "they want to refresh. You will be given a small shortlist of "
        "interest-kind topics from a shared knowledge graph; your job is "
        "to choose between 6 and 10 of them to show, in priority order, "
        "with a one-line 'why we're suggesting this' for each.\n"
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
        "- why_suggested_md is ONE sentence, at most 110 characters, "
        "  written like a knowledgeable peer (not a marketing line). "
        "  Mention the connection where relevant — e.g. 'Builds on the "
        "  multivariable calculus you flagged for refresh.' or 'A natural "
        "  follow-on if you're rebuilding solid-state intuition.' Plain "
        "  prose, no labels, no exclamation marks.\n"
        "- If the relationship cards lean 'reconnecting' or 'follow this "
        "  field', favour suggestions that pull in current/active areas. "
        "  If they lean 'curious', favour conceptually accessible entries.\n"
        "- Do not condescend, do not assume the user is a beginner."
    )


def build_user_prompt(
    *,
    domain_chips: list[str],
    relationship_cards: list[str],
    short_text: str,
    marked_foundation_titles: list[str],
    shortlist: list[dict],
) -> str:
    chips_block = ", ".join(domain_chips) if domain_chips else "(none)"
    cards_block = "; ".join(relationship_cards) if relationship_cards else "(none)"
    text_block = short_text.strip() if short_text and short_text.strip() else "(none)"
    marked_block = (
        ", ".join(marked_foundation_titles) if marked_foundation_titles else "(none)"
    )
    lines = "\n".join(
        f'- slug="{c["slug"]}" title="{c["title"]}" '
        f'desc="{(c.get("description_md") or "")[:140]}" '
        f'prereq_overlap={c.get("prereq_overlap_count", 0)}'
        for c in shortlist
    )
    return (
        f"User's domain chips: {chips_block}\n"
        f"User's relationship cards: {cards_block}\n"
        f"User's optional background note: \"{text_block}\"\n"
        f"Foundations the user flagged for refresh: {marked_block}\n"
        f"\n"
        f"Shortlist of interest-kind nodes (pick 6–10 of these):\n{lines}"
    )
