"""Prompt builders for /generate-edge-description.

Produces a short paragraph naming 2-3 specific bridging concepts so the
skill-tree EdgePanel reads as substantive rather than as a restated
header. Generated once per edge, cached, shared across users.
"""

SYSTEM_PROMPT = """You are explaining why two concepts are connected in a science curriculum.

The reader is looking at an edge in their skill tree and wants to understand the substance of the connection — not just the abstract label ('prerequisite' / 'related') but what specifically transfers from one to the other. They are a working professional, intelligent and capable, but they may be new to one or both of these areas.

# Output format

You MUST respond with a single JSON object — no prose, no markdown fences. The object has one field:

- "description_md": string. Three to five sentences of plain-language markdown explaining the connection. Name 2-3 specific concepts, results, or skills from the source that load-bear into the target. Be concrete — "band theory and Bloch's theorem" beats "core ideas from solid state". LaTeX ($...$) is allowed for inline math when natural; avoid display math. No bulleted lists; this is prose.

# Hard rules

- The framing of the connection MUST match the relationship type:
  - For `prerequisite`: explain what skills/concepts from the source the reader will lean on when working with the target.
  - For `related`: explain what conceptual overlap or mutual reinforcement makes time on one deepen the other. Neither side is required for the other.
- Output ONLY the JSON object. No leading or trailing text, no markdown fences.
- Be warm and grounded — like a colleague pointing out a connection they find interesting. Not textbook prose, not marketing copy.
- Do not introduce technical terms without enough context for someone new to follow.
- Do not repeat the node titles back as a sentence ('X is a prerequisite for Y' is forbidden — the reader sees the titles in the panel header)."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def _format_node(label: str, title: str, description_md: str, subtopics: list[str]) -> str:
    subtopic_line = (
        "  Subtopics: " + ", ".join(subtopics) if subtopics else "  (no subtopics listed)"
    )
    return (
        f"{label}: {title}\n"
        f"  Description: {description_md or '(empty)'}\n"
        f"{subtopic_line}"
    )


def build_user_prompt(
    *,
    edge_kind: str,
    source_title: str,
    source_description_md: str,
    source_subtopics: list[str],
    target_title: str,
    target_description_md: str,
    target_subtopics: list[str],
) -> str:
    return (
        f"Relationship: {edge_kind}\n\n"
        f"{_format_node('Source', source_title, source_description_md, source_subtopics)}\n\n"
        f"{_format_node('Target', target_title, target_description_md, target_subtopics)}"
    )
