"""Prompts for POST /add-interest.

Both system prompts are short and stable so prompt-cache applies across calls.
Dynamic data (raw_text, candidate list, existing slugs) travels in the user message.
"""

from __future__ import annotations


def build_dedup_system_prompt() -> str:
    return (
        "You are deduplicating a user's interest expression against an existing knowledge graph. "
        'Return ONLY a JSON object: {"verdict": "same"|"related"|"new", '
        '"matched_node_slug": null|"string", "reason": "string"}. '
        'Use "same" when the interest clearly IS an existing node. '
        'Use "related" when it is adjacent but distinct — set matched_node_slug to the closest slug. '
        'Use "new" when there is no meaningful match. '
        "Never invent a slug not present in the candidate list. "
        "matched_node_slug must be null for a new verdict."
    )


def build_dedup_user_prompt(raw_text: str, candidates: list[dict]) -> str:
    if candidates:
        lines = "\n".join(
            f'- slug="{c["slug"]}" title="{c["title"]}" '
            f'description="{(c.get("description_md") or "")[:120]}"'
            for c in candidates
        )
        candidates_block = f"Candidate nodes:\n{lines}"
    else:
        candidates_block = "Candidate nodes: (none)"
    return f'User expressed interest in: "{raw_text}"\n\n{candidates_block}'


def build_generate_system_prompt() -> str:
    return (
        "You are expanding a personalized science learning graph for a working professional. "
        "Generate a new interest node for the topic the user described. "
        "Return ONLY a JSON object with these exact keys: "
        '{"title": "string", "slug": "string", "description_md": "string", '
        '"domain": "math"|"physics"|"applied", "difficulty_hint": "intro"|"core"|"advanced", '
        '"subtopics": ["string", ...], "proposed_prerequisite_slugs": ["string", ...]}. '
        "slug must be lowercase kebab-case ASCII and must not appear in the existing-slugs list. "
        "proposed_prerequisite_slugs must only contain slugs from the existing-slugs list. "
        "subtopics are short display names (3–6 words), not slugs. "
        "description_md: 2–3 sentences of plain markdown, no LaTeX."
    )


def build_generate_user_prompt(
    raw_text: str,
    existing_slugs: list[str],
    related_slug: str | None,
) -> str:
    slugs_block = ", ".join(existing_slugs) if existing_slugs else "(none)"
    related_note = (
        f'\nThe user\'s interest is related to the existing node "{related_slug}". '
        "Generate a distinct node for the new topic; you may include that slug in "
        "proposed_prerequisite_slugs if it is genuinely a prerequisite."
        if related_slug
        else ""
    )
    return (
        f'User expressed interest in: "{raw_text}"{related_note}\n\n'
        f"Existing slugs (your slug must not duplicate these): {slugs_block}"
    )
