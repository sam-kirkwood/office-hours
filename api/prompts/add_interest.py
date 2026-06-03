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
        '    "kind": "interest" | "concept",\n'
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
        "- kind='concept' when the user is asking about a sub-node-level idea "
        "  rather than a new area of study — e.g. 'I forgot what power means', "
        "  'remind me what eigenvectors are', 'what does entropy actually mean'. "
        "  These are concept-level refreshers, not new interests; the UI will "
        "  surface a single explanatory problem and will NOT create a new node "
        "  or run the dialog. kind='interest' is the default for everything "
        "  else — a topic, a field, a paper-following ambition. If unsure, "
        "  prefer 'interest'.\n"
        "- specificity='specific' when the user has named the angle they care "
        "  about (e.g. 'I want to follow LIGO papers', 'I want my ODEs back'). "
        "  specificity='ambiguous' when the topic is broad enough that several "
        "  legitimate angles exist (e.g. 'I want to learn semiconductors').\n"
        "- implicit_intent infers from language: 'I want my X back' → refresh; "
        "  'I want to learn X' / 'I'm curious about X' → teach; 'I want harder "
        "  problems on X' / 'I want to go deeper' → consolidate.\n"
        "- Explicit denial of current mastery combined with want-to-learn "
        "  language → teach, NOT consolidate. Examples: 'I want to actually "
        "  understand X', 'I want to stop hand-waving X', 'I want to know X "
        "  properly instead of just referencing it', 'I want to understand X "
        "  instead of just dropping the words' → all teach. consolidate is "
        "  reserved for users who assert existing mastery and want harder "
        "  work; phrasing that confesses the user does NOT yet understand the "
        "  material is teach even when the topic itself is advanced.\n"
        "- mirror_back_md is one or two short sentences in natural language. "
        "  Use the user's own words where possible. No data summary, no labels.\n"
        "- For specific segments: set optional_followup_md to a short, "
        "  skippable invitation (e.g. 'Want to tell me more about what draws "
        "  you to this?'). Leave path_options as [].\n"
        "- For ambiguous segments: leave optional_followup_md null and provide "
        "  3 to 5 path_options, each with a short kebab-case key, a label of "
        "  at most 80 characters in natural language, and a draft_intent_context "
        "  that captures what the resolved intent would be if the user picks "
        "  that path (same shape as the segment-level draft_intent_context — see "
        "  below). Always end with an implicit 'or something else' — do not "
        "  add an explicit other option, the UI will provide one.\n"
        "- dedup.verdict = 'same' when the segment clearly maps to one of the "
        "  candidate nodes. 'related' when the topic is adjacent but distinct "
        "  (different level, different sub-area). 'new' when no candidate is "
        "  even remotely relevant. Never invent a slug not in the candidate "
        "  list. matched_node_slug must be null for 'new'.\n"
        "- draft_intent_context is 1–2 sentences of natural prose describing "
        "  THIS USER'S goal and angle for this interest. It will be shown to "
        "  the user on their profile page AND read by the problem generator, "
        "  so it must read like a sentence, not a tag list. Write in plain "
        "  declarative prose. DO NOT use template fragments like 'teach intent', "
        "  'refresh intent', or '<slug> node' — those leak machinery into the "
        "  user's view. Examples of GOOD draft_intent_context: "
        "  'Wants to follow LIGO papers and where gravitational-wave detection "
        "  is heading. Papers-heavy preference.' / "
        "  'Reconnecting with ODEs after years away — wants to refresh the "
        "  math, especially separable equations and linear systems.' / "
        "  'Curious about how transistors and circuits actually work, starting "
        "  from the device-physics angle rather than abstract semiconductor "
        "  theory.' Capture the user's intent (whether they're learning fresh, "
        "  refreshing, or consolidating) through the words you choose, not "
        "  through enum-like phrases.\n"
        "- Be calibrated: this is a knowledgeable peer talking, not a survey "
        "  form. No 'thank you for your response' phrasing."
    )


def build_rewrite_summary_system_prompt() -> str:
    return (
        "You write user-facing summaries that describe what an interest topic "
        "covers — the kind of subtitle you'd see on a card. The summary "
        "describes the topic itself (concepts, techniques, questions it "
        "addresses), tilted toward this user's stated angle when there is "
        "one. It is NOT a restatement of what the user wants to do.\n"
        "\n"
        "Return ONLY a JSON object of this exact shape:\n"
        '{"summaries": [\n'
        '  {"user_interest_id": "uuid-string", "summary": "string"}\n'
        "]}\n"
        "\n"
        "FORM: Lead with the node title verbatim, a colon, then 1–2 sentences "
        "of descriptive content. The colon-clause names the actual ideas the "
        "topic engages with, in plain declarative prose.\n"
        "\n"
        "GROUNDING: Use node_description_md and subtopics to anchor the "
        "summary in real content. Don't invent scope the topic doesn't have. "
        "If subtopics name specific techniques or concepts, surface a couple "
        "of them in the summary.\n"
        "\n"
        "USER ANGLE: If current_context names a specific tilt (e.g. 'follow "
        "LIGO papers', 'focus on superconductors', 'reconnecting after years "
        "away'), bias the description toward that angle — pick subtopics or "
        "framings that match. If current_context is empty or just says "
        "things like 'wants to learn X' / 'X foundations' with no specific "
        "angle, write a general descriptive summary that names the core of "
        "the topic.\n"
        "\n"
        "FORBIDDEN openings — do not start with these or paraphrase them:\n"
        "- 'Wants to learn …'\n"
        "- 'Wants to refresh …'\n"
        "- 'Wants to explore …'\n"
        "- 'The user wants …'\n"
        "- 'An interest in …'\n"
        "- 'Looking to study …'\n"
        "These are statements about the user; the summary is about the "
        "TOPIC.\n"
        "\n"
        "EXAMPLES of GOOD summaries:\n"
        "- 'Solid State Physics: how conductors, insulators, and "
        "  semiconductors work and how they integrate into modern electronic "
        "  devices.'\n"
        "- 'Partial Differential Equations: the math of fields that vary in "
        "  space and time — heat flow, wave propagation, and quantum "
        "  systems.'\n"
        "- 'Gravitational Wave Detection & LIGO: how interferometry measures "
        "  spacetime distortions from black-hole and neutron-star mergers, "
        "  with a focus on following the detection papers as the field "
        "  evolves.'\n"
        "- 'Bayesian Filtering & Kalman Methods: probabilistic state "
        "  estimation for systems evolving under noisy dynamics — from "
        "  navigation and tracking to robotics.'\n"
        "- 'Quantum Mechanics — Spin, Perturbation, and Scattering: "
        "  angular momentum, perturbation theory, scattering, and identical "
        "  particles — the apparatus you need before reading modern "
        "  condensed-matter or particle physics.'\n"
        "\n"
        "EXAMPLES of BAD (do not produce):\n"
        "- 'Wants to learn solid state physics and its core principles.'\n"
        "- 'Wants to explore quantum gravity theories.'\n"
        "- 'The user is interested in PDEs.'\n"
        "\n"
        "Output exactly one entry per input, in the same order, with the "
        "user_interest_id echoed verbatim."
    )


def build_rewrite_summary_user_prompt(items: list[dict]) -> str:
    lines: list[str] = []
    for it in items:
        subtopics = it.get("subtopics") or []
        subtopics_str = "; ".join(subtopics) if subtopics else "(none)"
        desc = (it.get("node_description_md") or "").strip().replace("\n", " ")
        if len(desc) > 400:
            desc = desc[:400] + "…"
        if not desc:
            desc = "(no description)"
        lines.append(
            "---\n"
            f'user_interest_id: "{it["user_interest_id"]}"\n'
            f'node_title: "{it["node_title"]}"\n'
            f'node_description_md: "{desc}"\n'
            f'subtopics: {subtopics_str}\n'
            f'current_context: "{it.get("current_context", "")}"'
        )
    return (
        "Write a card-subtitle summary for each interest below. Form: "
        "'<node_title>: <descriptive content>.' Ground in node_description_md "
        "and subtopics; tilt by current_context if it carries a real angle.\n\n"
        + "\n".join(lines)
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
