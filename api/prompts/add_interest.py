"""Prompts for the add-interest dialog (survey-and-difficulty-design.md §2).

Two flows:

  /parse   — Haiku. Splits raw_text into segments, classifies each as
             specific|ambiguous, classifies implicit intent, runs dedup
             against a candidate slice of the megagraph, and writes the
             mirror-back + path options.

  /resolve — Sonnet. Only invoked when the resolved interest needs a new
             interest node (dedup verdict = 'new' or 'related'). Generates
             the node and a one-sentence entry-point preview.

System prompts are short and stable so the prompt cache applies across
calls. All dynamic data (raw_text, candidates, slugs) goes in the user
message.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# /parse — Haiku parse
# ---------------------------------------------------------------------------


def build_parse_system_prompt() -> str:
    return (
        "You analyse a learner's free-text expression of what they want to study, "
        "split it into distinct interests where appropriate, and report back in "
        "a structured JSON object that a follow-up UI will render.\n"
        "\n"
        "Return ONLY a JSON object of this exact shape:\n"
        '{"segments": [\n'
        "  {\n"
        '    "raw_text_segment": "string",\n'
        '    "specificity": "specific" | "ambiguous",\n'
        '    "implicit_intent": "teach" | "refresh" | "consolidate",\n'
        '    "mirror_back_md": "string",\n'
        '    "optional_followup_md": "string" | null,\n'
        '    "path_options": [\n'
        '      {"key": "kebab-slug", "label_md": "string", "draft_intent_context": "string"}\n'
        "    ],\n"
        '    "dedup": {"verdict": "same" | "related" | "new", "matched_node_slug": "string" | null},\n'
        '    "draft_intent_context": "string"\n'
        "  }\n"
        "]}\n"
        "\n"
        "Rules:\n"
        "- If the user names two or more clearly distinct subjects (e.g. "
        "  'quantum mechanics AND thermodynamics'), produce one segment per "
        "  subject. Coarse-grained is fine when the megagraph is sparse; only "
        "  split when the subjects are genuinely separate, not when one is a "
        "  subtopic of the other.\n"
        "- specificity='specific' when the user has named the angle they care "
        "  about (e.g. 'I want to follow LIGO papers', 'I want my ODEs back'). "
        "  specificity='ambiguous' when the topic is broad enough that several "
        "  legitimate angles exist (e.g. 'I want to learn semiconductors').\n"
        "- implicit_intent infers from language: 'I want my X back' → refresh; "
        "  'I want to learn X' / 'I'm curious about X' → teach; 'I want harder "
        "  problems on X' / 'I want to go deeper' → consolidate.\n"
        "- mirror_back_md is one or two short sentences in natural language. "
        "  Use the user's own words where possible. No data summary, no labels.\n"
        "- For specific segments: set optional_followup_md to a short, "
        "  skippable invitation (e.g. 'Want to tell me more about what draws "
        "  you to this?'). Leave path_options as [].\n"
        "- For ambiguous segments: leave optional_followup_md null and provide "
        "  3 to 5 path_options, each with a short kebab-case key, a label of "
        "  at most 80 characters in natural language, and a draft_intent_context "
        "  that captures what the resolved intent would be if the user picks "
        "  that path. Always end with an implicit 'or something else' — do not "
        "  add an explicit other option, the UI will provide one.\n"
        "- dedup.verdict = 'same' when the segment clearly maps to one of the "
        "  candidate nodes. 'related' when the topic is adjacent but distinct "
        "  (different level, different sub-area). 'new' when no candidate is "
        "  even remotely relevant. Never invent a slug not in the candidate "
        "  list. matched_node_slug must be null for 'new'.\n"
        "- draft_intent_context is a short text string (one or two clauses) "
        "  capturing the user's path + intent if they accept the parse without "
        "  clarifying. Examples: 'research-following angle, papers-heavy'; "
        "  'devices-and-circuits angle, teach intent'; 'refresh ODE foundations'. "
        "  Not a hardcoded enum — write what fits.\n"
        "- Be calibrated: this is a knowledgeable peer talking, not a survey "
        "  form. No 'thank you for your response' phrasing."
    )


def build_parse_user_prompt(raw_text: str, candidates: list[dict]) -> str:
    if candidates:
        lines = "\n".join(
            f'- slug="{c["slug"]}" title="{c["title"]}" kind="{c.get("kind","")}" '
            f'desc="{(c.get("description_md") or "")[:120]}"'
            for c in candidates
        )
        candidates_block = f"Candidate nodes (megagraph slice):\n{lines}"
    else:
        candidates_block = "Candidate nodes: (none — graph is empty or no overlap)"
    return f'User typed: "{raw_text}"\n\n{candidates_block}'


# ---------------------------------------------------------------------------
# /resolve — Sonnet node generation (only for verdict='new' or 'related')
# ---------------------------------------------------------------------------


def build_generate_system_prompt() -> str:
    return (
        "You are expanding a personalised science learning graph for a working "
        "professional. Generate a new interest node for the topic the user has "
        "resolved to. The node lives in a shared megagraph used by ~30 trusted "
        "users; later operator curation may merge or refine it.\n"
        "\n"
        "Return ONLY a JSON object with these exact keys:\n"
        '{"title": "string", "slug": "string", "description_md": "string", '
        '"domain": "math"|"physics"|"applied", '
        '"difficulty_hint": "intro"|"core"|"advanced", '
        '"subtopics": ["string", ...], '
        '"proposed_prerequisite_slugs": ["string", ...], '
        '"entry_point_preview_md": "string"}\n'
        "\n"
        "Rules:\n"
        "- slug: lowercase kebab-case ASCII; must not appear in existing-slugs.\n"
        "- title: case-insensitively distinct from every entry in existing-titles.\n"
        "- description_md: 2–3 sentences of plain markdown, no LaTeX. Capture "
        "  what the topic IS and why someone would care, not what level it's "
        "  taught at.\n"
        "- subtopics: 4–8 short display names (3–6 words each), the major "
        "  conceptual chunks of the topic. Not slugs.\n"
        "- proposed_prerequisite_slugs: only slugs present in existing-slugs. "
        "  Genuine prerequisites only; do not pad. Empty list is fine.\n"
        "- entry_point_preview_md: ONE sentence naming what a conceptual "
        "  entry-point problem or paper for this topic would address. Example: "
        "  'a conceptual entrance to gravitational-wave detection — what LIGO "
        "  is measuring and why interferometry works'. The user will see this "
        "  rendered into 'Your first item will be: …'."
    )


def build_generate_user_prompt(
    *,
    final_intent_text: str,
    intent_context: str,
    existing_slugs: list[str],
    existing_titles: list[str],
    related_slug: str | None,
) -> str:
    slugs_block = ", ".join(existing_slugs) if existing_slugs else "(none)"
    titles_block = "; ".join(existing_titles) if existing_titles else "(none)"
    related_note = (
        f'\nThe resolved interest is related to existing node "{related_slug}". '
        "Generate a distinct node; you may include that slug in "
        "proposed_prerequisite_slugs if it is genuinely a prerequisite."
        if related_slug
        else ""
    )
    return (
        f'Resolved intent: "{final_intent_text}"\n'
        f'Soft intent context (already stored on the user_interests row): '
        f'"{intent_context}"{related_note}\n\n'
        f"Existing slugs (your slug must not duplicate any): {slugs_block}\n"
        f"Existing titles (case-insensitively distinct): {titles_block}"
    )
