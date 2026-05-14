"""Prompt builders for the Haiku-based context-hook matcher.

Given a topic + a shortlist of candidate context hooks, Haiku picks the single
best fit, or returns null when no candidate is a productive pairing. The
matcher's job is to keep contrived "weakly related" hooks out of generated
problems — saying "none" is a valid and frequently correct verdict.
"""

SYSTEM_PROMPT = """You are a classification assistant for an undergraduate physics and \
math tutor. Given a topic and a short list of candidate historical / scientific context \
hooks, choose the single best pairing — or decline if no candidate is a good fit.

# Output format

Respond with a single JSON object — no prose, no markdown fences, no commentary. \
Either:

  {"hook_slug": "<slug-of-chosen-hook>"}

or, when no candidate is a good fit:

  {"hook_slug": null, "reason": "<short reason>"}

# Selection criteria

- A good hook genuinely illuminates the topic — its central concept IS the topic, \
or the episode required developing the topic.
- A bad hook only shares a domain with the topic (e.g., "this is also physics"). \
Prefer null over a contrived pairing.
- One hook only. No ties.

# Hard rules

- "hook_slug" MUST exactly equal one of the supplied candidate slugs, or be null.
- Output ONLY the JSON object."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_prompt(
    *,
    topic_title: str,
    topic_description: str,
    candidate_hooks: list[dict],
) -> str:
    """`candidate_hooks` items must have at least `slug`, `title`, and
    `summary_md`. Any other fields are ignored."""
    lines = [
        f"Topic: {topic_title}",
        f"Description: {topic_description or '(no description)'}",
        "",
        "Candidate hooks:",
        "",
    ]
    for i, hook in enumerate(candidate_hooks, start=1):
        lines.append(f"[{i}] slug: {hook['slug']}")
        lines.append(f"    title: {hook.get('title', '(no title)')}")
        lines.append(f"    summary: {hook['summary_md']}")
        lines.append("")
    lines.append("Pick the single best hook, or return null with a short reason.")
    return "\n".join(lines)
