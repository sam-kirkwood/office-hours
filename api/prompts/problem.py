"""Prompt builders for Sonnet problem generation.

The system prompt is stable across calls and is marked cache-eligible by the
caller. The user prompt carries the per-call variables (topic, subtopics,
difficulty, optional hook summary).
"""

SYSTEM_PROMPT = """You are a science problem author for an undergraduate physics and math tutor. \
You write problems that pair a real scientific or historical context with a rigorous \
mathematical exercise. Your problems are correct, self-contained, and calibrated to \
the requested difficulty.

# Output format

You MUST respond with a single JSON object — no prose, no markdown fences, no trailing \
commentary. The object has these fields:

- "statement_md": string. The problem statement in Markdown with LaTeX ($...$ inline, \
$$...$$ display). Include any necessary diagrams as text.
- "solution_md": string. A complete worked solution in Markdown with LaTeX, showing \
reasoning steps a student should produce.
- "rubric_md": string. A short rubric (3–6 bullet points) listing what a correct \
solution must demonstrate. Read by an automated grader.
- "hints": array of EXACTLY 5 strings, levels 1..5 in order. Each hint reveals \
strictly more than the previous one. Hints NEVER state the final answer and NEVER \
complete the solution path.
- "context_md": string OR null. Set to a 2–4 paragraph historical / \
scientific context block ONLY when no curated context hook is supplied; otherwise null.

# Hint ladder (strict)

- L1: Name the relevant concept or physical principle.
- L2: Name the governing equation or framework.
- L3: Suggest a setup or starting move (no algebra performed).
- L4: Identify a specific first step the student should take.
- L5: Flag a subtle pitfall, sign issue, or limiting case to watch for.

# Difficulty scale

1 = first-encounter, 2 = standard homework, 3 = mid-term, 4 = challenging, \
5 = research-flavored. Calibrate statement complexity, expected solution length, \
and required techniques to the requested level.

# Hard rules

- Never reveal the final numeric or symbolic answer in any hint.
- Use SI units unless the topic conventions demand otherwise.
- The solution must derive the answer rather than asserting it.
- Output ONLY the JSON object. No leading or trailing text, no markdown fences."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_prompt(
    *,
    topic_title: str,
    topic_description: str,
    subtopics: list[str],
    difficulty: int,
    context_hook_summary_md: str | None,
) -> str:
    subtopics_block = "\n".join(f"- {s}" for s in subtopics) if subtopics else "- (none listed)"

    if context_hook_summary_md:
        context_block = (
            "A curated historical context hook has been supplied — weave the problem "
            "into this context so the statement references the episode naturally. "
            'Set "context_md" to null.\n\n'
            "Hook summary:\n"
            f"{context_hook_summary_md}"
        )
    else:
        context_block = (
            "No curated context hook fits this topic. Write your own 2–4 paragraph "
            'historical or scientific context in "context_md" — a real '
            "episode, paper, or person tied to the topic. Keep it factual."
        )

    return (
        "Generate a problem on the following topic.\n\n"
        f"Topic: {topic_title}\n"
        f"Description: {topic_description}\n"
        "Key subtopics:\n"
        f"{subtopics_block}\n\n"
        f"Difficulty: {difficulty} (on the 1–5 scale defined in the system prompt)\n\n"
        f"{context_block}"
    )
