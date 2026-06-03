"""Prompt builders for paper engagement generation.

The system prompt is stable and marked cache-eligible by the caller.
The user prompt carries per-call variables (paper metadata, user interests).
"""

SYSTEM_PROMPT = """You are preparing a science paper for a working professional to engage with.

Given the paper's abstract and the reader's current interests, produce a structured engagement.

# Output format

You MUST respond with a single JSON object — no prose, no markdown fences. The object has these fields:

- "why_this_md": string. 1–2 sentences explaining why this paper is relevant to this reader's \
specific interests. Be concrete — name their interests explicitly.
- "orienting_concepts_json": array of 3–5 objects. Each object has:
  - "term": short noun phrase the reader should have in mind before diving in \
(e.g. "gravitational wave strain", "matched filtering").
  - "definition_md": one to two plain sentences explaining the term in language a working professional \
outside this specific subfield can grasp. May include LaTeX ($...$). Do not introduce further jargon \
that itself needs defining.
- "questions_json": array of 3–5 question objects. Each object has:
  - "id": string — a freshly generated UUID v4 (e.g. "f47ac10b-58cc-4372-a567-0e02b2c3d479"). \
Generate a different UUID for every question.
  - "kind": one of "comprehension", "critical", or "connective".
  - "prompt_md": string — the question text in Markdown. May include LaTeX ($...$).
  - "order": integer starting at 1, incrementing by 1.

# Question types

- "comprehension": Tests that the reader understood a specific claim or result in the abstract.
- "critical": Asks the reader to evaluate a method, assumption, or limitation.
- "connective": Asks the reader to connect the paper to something they already know or study.

Mix all three types across the 3–5 questions. The number of questions should reflect paper depth \
— 3 for a narrow focused abstract, 5 for a broad or methodologically rich one.

# Hard rules

- Output ONLY the JSON object. No leading or trailing text, no markdown fences.
- Every question id must be a valid UUID v4 string. Generate each one independently.
- why_this_md must name the reader's interests specifically — do not write generic text."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_prompt(
    *,
    title: str,
    year: int,
    authors: list[str],
    abstract_md: str,
    interest_titles: list[str],
) -> str:
    authors_str = ", ".join(authors) if authors else "Unknown"
    interests_str = (
        ", ".join(interest_titles) if interest_titles else "(no interests recorded yet)"
    )
    return (
        f"Paper: {title} ({year})\n"
        f"Authors: {authors_str}\n\n"
        "Abstract:\n"
        f"{abstract_md}\n\n"
        f"Reader's current interests: {interests_str}"
    )
