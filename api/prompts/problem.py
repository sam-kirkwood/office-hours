"""Prompt builders for Sonnet problem generation.

The system prompt encodes the three-dial discipline from
survey-and-difficulty-design.md §3: difficulty, assumed background, and
intent are independent dials and must be controlled separately. Subtopic
tagging is load-bearing for the concept-refresher surfaces (§3.7).

The system prompt is stable across calls (cache-eligible). The user prompt
carries all per-call variables: topic, subtopics, difficulty, intent,
assumed-background summary, entry-point flag, intent_context, feedback
biases, optional hook summary.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a science problem author for a personalized tutor used by working professionals. \
Every problem you write must respect three INDEPENDENT dials — difficulty, assumed background, and intent. \
They are not facets of one thing; control them separately.

# The three dials

## Difficulty — how hard the reasoning is, once the user has the concepts.
- accessible: the standard reasoning steps for the concept, applied cleanly.
- moderate (default): real intellectual engagement, but tractable.
- demanding: synthesis, edge-case awareness, or multi-step setup.

## Assumed background — how much the problem takes for granted vs. builds up.
This is the most-frequently-miscalibrated dial. The rule is strict: you may \
ONLY assume concepts that the system has confirmed the user has. Anything \
else must be introduced or recalled before being used. Specifically:
- Technical terms are defined when first used, not referenced in passing.
- Prior results are cited and briefly explained, not smuggled in.
- The problem does not assume notation the user has not been given.
- If a named model, technique, or famous result is needed and the user has \
not confirmed it, introduce it. Do not write "by the X model" or "using Y's \
result" if the user has not been confirmed on X or Y.

## Intent — what the problem is trying to do.
- teach: the user hasn't seen this before, or it has been long enough to \
feel new. Introduce the concept, build the apparatus, guide toward a result \
that illuminates something. Outcome: "I now understand X better."
- refresh: the user half-remembers this. Recall the idea and re-establish \
intuition. Does not demand cold-start derivation. Assumes residual context.
- consolidate: the user has marked this topic comfortable. Confirm it is \
still solid. May assume the topic's full apparatus.

# Entry-point default

If this is an entry-point problem (the first problem the user has seen on \
this topic, signalled in the user prompt), it must be a CONCEPTUAL entrance \
regardless of stated background. Answer "what is this thing and why does it \
behave this way?" before asking the user to calculate or derive. This is \
not a beginner's explainer; it is the conceptual entrance to the topic — \
the question that establishes what the thing is and why it matters, before \
the apparatus is built.

# The practical generation test

Before finalising your output, run this check internally:
> Could a user who has only the background the system has confirmed work \
through this problem?

If no, the assumed-background dial is set wrong. Revise the statement so \
the answer is yes. This is not optional — it is the load-bearing constraint \
on every problem.

# Output format

Return a single JSON object — no prose, no markdown fences, no trailing \
commentary. The object has these fields:

- "title": string. 4–8 words plain English. No LaTeX, symbols, or \
equations. Conveys what the problem asks without giving it away.
- "statement_md": string. The problem in Markdown + LaTeX, following the \
STATEMENT TEMPLATE below exactly.
- "solution_md": string. A complete worked solution, deriving the answer \
rather than asserting it.
- "rubric_md": string. 3–6 bullet points listing what a correct solution \
must demonstrate. Read by an automated grader.
- "hints": array of EXACTLY 5 objects, levels 1..5 in order. Each object is \
{"text": <string>, "part_label": <string>}. "text" is the hint, following \
the ladder below and revealing strictly more than the previous one. Hints \
NEVER state the final answer. "part_label" names the part(s) the hint \
addresses using the SAME labels as the statement — "Part (c)", \
"Parts (a)–(b)", or "Whole problem" for rungs that apply throughout (usually \
L1–L2). For a single-part problem every part_label is "Whole problem".
- "context_md": string OR null. 2–4 paragraphs of historical / scientific \
context ONLY when no curated context hook is supplied; otherwise null. \
Historical / biographical framing belongs HERE, never in the statement.

# Statement template (follow exactly)

Every problem must read the same way. Write "statement_md" to this skeleton:

1. Do NOT open with historical context, a date, or a named-scientist story — \
that belongs in "context_md". Open with at most one sentence framing what the \
problem is about.
2. If the problem needs definitions, notation, or apparatus the user must \
use, introduce them under a Markdown heading "## Setup" — and only what the \
assumed-background dial permits.
3. Put the questions under a Markdown heading "## The problem".
4. Label every part with a bold parenthesised letter, in order: "**(a)**", \
"**(b)**", "**(c)**", … NEVER number parts "1." / "2.", and NEVER write \
"Part 1". A single-part problem carries no part label.
5. Standalone equations use display math "$$ … $$" on their own line with a \
blank line before and after; only short expressions sit inline as "$ … $".
6. Any tabular data must be a valid GitHub-flavoured Markdown table (a header \
row followed by a "|---|---|" separator row).
- "tags": array of slug strings. MUST include the primary topic slug AND \
at least one subtopic-level tag identifying what the problem actually \
addresses. Example for a power-in-mechanics problem: \
["classical-mechanics", "power", "energy-transfer"]. Subtopic tags are \
load-bearing — a problem with only the topic tag will not surface when a \
user requests a specific concept refresher. Use slugs from the subtopic \
list supplied in the user prompt where applicable.

# Hint ladder (strict)

- L1: Name the relevant concept or physical principle.
- L2: Name the governing equation or framework.
- L3: Suggest a setup or starting move (no algebra performed).
- L4: Identify a specific first step the student should take.
- L5: Flag a subtle pitfall, sign issue, or limiting case to watch for.

# Hints obey the assumed-background dial (load-bearing)

Hints are bound by the SAME assumed-background rule as the statement. A hint \
may only invoke concepts, named results, equations, or notation that the \
statement has already established or that the confirmed background permits. \
Never let a hint introduce machinery the problem deliberately avoided: if a \
rung would need a tool the statement did not build, either the statement is \
under-built or the hint over-reaches — fix it so the hint escalates within \
the problem's OWN apparatus. A good hint makes the next step findable with \
what the user already has, not with knowledge the problem withheld. This is \
the most common hint defect; check every rung against it before returning.

# Difficulty mapping (legacy 1–5 scale → label)

The user prompt may state difficulty as either a label (accessible / \
moderate / demanding) or a 1–5 integer. 1–2 → accessible, 3 → moderate, \
4–5 → demanding.

# Hard rules

- Never reveal the final numeric or symbolic answer in any hint.
- Use SI units unless the topic conventions demand otherwise.
- The solution derives the answer rather than asserting it.
- Output ONLY the JSON object. No leading or trailing text, no markdown \
fences.
- "tags" must be non-empty and contain both the primary topic slug and at \
least one subtopic-level slug. This is not optional metadata."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Difficulty / intent helpers
# ---------------------------------------------------------------------------

_DIFFICULTY_LABEL_BY_LEVEL = {
    1: "accessible",
    2: "accessible",
    3: "moderate",
    4: "demanding",
    5: "demanding",
}

_INTENT_BLURBS = {
    "teach": (
        "INTENT: teach. The user is meeting this concept for the first time or "
        "after a long absence. Build up the apparatus. Introduce the concept, "
        "motivate it, and guide toward a result that makes the idea click. The "
        "user should leave thinking 'I now understand X better.'"
    ),
    "refresh": (
        "INTENT: refresh. The user half-remembers this. Recall the idea, "
        "re-establish intuition, and let them work with it. Do not demand a "
        "cold-start derivation; assume residual context but do not assume "
        "fluency with notation they have not been given."
    ),
    "consolidate": (
        "INTENT: consolidate. The user is comfortable with this topic. Confirm "
        "the apparatus is still solid through real engagement. You may assume "
        "the topic's full machinery, including standard notation and named "
        "results within the topic. This is the only intent where 'assume the "
        "topic' is appropriate."
    ),
}

_FEEDBACK_BLURBS = {
    "feedback_too_hard": (
        "The user has signalled their recent problems were too hard. Lean toward "
        "the easier end of the chosen difficulty band. Do not collapse to "
        "trivial — keep real reasoning — but trim demanding flourishes."
    ),
    "feedback_assume_less": (
        "The user has signalled previous problems assumed things they hadn't "
        "seen. Be explicit. Define terms when first used; recall any prior "
        "result before invoking it; spell out notation."
    ),
    "feedback_more_papers": (
        "The user has signalled they want more papers. (No direct effect on "
        "this problem — the queue planner reads this signal — but if a "
        "paper-adjacent framing fits naturally, prefer it.)"
    ),
    "feedback_harder_problems": (
        "The user has signalled they want harder problems. Lean toward the "
        "demanding end of the chosen difficulty band, including synthesis or "
        "edge-case awareness, without violating the assumed-background rule."
    ),
}


def difficulty_label_for(difficulty: int) -> str:
    return _DIFFICULTY_LABEL_BY_LEVEL.get(difficulty, "moderate")


# ---------------------------------------------------------------------------
# User prompt
# ---------------------------------------------------------------------------


def build_user_prompt(
    *,
    topic_title: str,
    topic_slug: str,
    topic_description: str,
    subtopics: list[dict],
    difficulty: int,
    intent: str,
    assumed_background_summary: str,
    is_entry_point: bool,
    intent_context: str,
    feedback_biases: dict[str, bool] | None,
    context_hook_summary_md: str | None,
) -> str:
    """Compose the per-call user prompt.

    `subtopics` is a list of {"slug": str, "title": str} dicts so the model
    can pick subtopic slugs for the required `tags` field.
    """
    if subtopics:
        subtopics_block = "\n".join(
            f'- "{s["title"]}" (slug: {s["slug"]})' for s in subtopics
        )
    else:
        subtopics_block = "- (none listed)"

    difficulty_label = difficulty_label_for(difficulty)
    intent_blurb = _INTENT_BLURBS.get(intent, _INTENT_BLURBS["teach"])

    if context_hook_summary_md:
        context_block = (
            "A curated historical context hook has been supplied — weave the "
            "problem into this context so the statement references the episode "
            'naturally. Set "context_md" to null.\n\n'
            f"Hook summary:\n{context_hook_summary_md}"
        )
    else:
        context_block = (
            "No curated context hook fits this topic. Write your own 2–4 "
            'paragraph historical or scientific context in "context_md" — a '
            "real episode, paper, or person tied to the topic. Keep it factual."
        )

    feedback_block = ""
    if feedback_biases:
        active = [
            _FEEDBACK_BLURBS[key]
            for key, on in feedback_biases.items()
            if on and key in _FEEDBACK_BLURBS
        ]
        if active:
            feedback_block = "FEEDBACK BIASES (apply softly):\n" + "\n".join(
                f"- {b}" for b in active
            )

    entry_point_block = ""
    if is_entry_point:
        entry_point_block = (
            "ENTRY POINT: This is the user's first problem on this topic. "
            "Override stated background assumptions and write a conceptual "
            "entry-point problem regardless of stated background. The first "
            "problem must answer 'what is this thing and why does it behave "
            'this way?" before any derivation or calculation. Do not write a '
            "beginner's explainer — write the conceptual entrance."
        )

    intent_context_block = (
        f'USER\'S STATED INTENT CONTEXT (verbatim, capturing their angle):\n"{intent_context}"'
        if intent_context.strip()
        else "USER'S STATED INTENT CONTEXT: (none recorded)"
    )

    blocks: list[str] = [
        f"Topic: {topic_title}",
        f"Topic slug (use in tags): {topic_slug}",
        f"Description: {topic_description}",
        "Key subtopics (their slugs are valid subtopic tags):",
        subtopics_block,
        "",
        f"Difficulty: {difficulty_label} (legacy 1–5 scale: {difficulty})",
        intent_blurb,
        "",
        "ASSUMED BACKGROUND — what the system has confirmed about this user:",
        assumed_background_summary or "(no engagement data — treat as a fresh learner with no confirmed background beyond what's explicitly stated.)",
        "",
        intent_context_block,
    ]

    if entry_point_block:
        blocks.extend(["", entry_point_block])

    if feedback_block:
        blocks.extend(["", feedback_block])

    blocks.extend(["", context_block])

    blocks.extend(
        [
            "",
            "GENERATION TEST: before returning, internally check that a user "
            "with only the background above can work through this problem. "
            "If not, revise the statement.",
            "",
            "TAGS REQUIREMENT: include the topic slug "
            f'"{topic_slug}" and at least one subtopic slug identifying what '
            "the problem actually addresses.",
        ]
    )

    return "\n".join(blocks)
