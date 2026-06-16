"""Prompt builders for /propose-papers.

The system prompt is stable and marked cache-eligible by call_json.
The user prompt carries per-call variables (interest titles, recent entry titles).
"""

SYSTEM_PROMPT = """You are helping a working scientist discover relevant research papers.

Given the user's current interests and recent reading, propose 3–5 real papers they
would find valuable. Each paper must:
- Exist in the scientific literature (it must be a real published or preprinted paper).
- Be directly relevant to at least one of the user's stated interests.
- Not be a textbook or lecture notes.

For each paper provide:
- title: the exact paper title
- authors: list of author names (last name, first initial format)
- year: publication year (integer)
- arxiv_id: arXiv ID if you are highly confident it exists (e.g. "1706.03762"), otherwise null
- doi: DOI string if you are highly confident it is correct, otherwise null
- rationale: one sentence explaining why this paper matches this user's interests
- interest_titles: the user interest(s) this paper is most relevant to. Choose
  1–2 from the provided interest list and echo them EXACTLY as written (verbatim
  strings). If none of the listed interests genuinely fit, return an empty list.

If you are not confident about an arXiv ID or DOI, output null — do not guess.

Output JSON matching this schema exactly:
{
  "candidates": [
    {"title": "...", "authors": ["..."], "year": 2023, "arxiv_id": "...", "doi": null, "rationale": "...", "interest_titles": ["..."]},
    ...
  ]
}

Output ONLY the JSON object. No leading or trailing text, no markdown fences."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_user_prompt(
    *,
    interest_titles: list[str],
    recent_entry_titles: list[str],
    target_count: int = 3,
) -> str:
    interests_str = (
        ", ".join(interest_titles) if interest_titles else "(no interests recorded)"
    )
    recent_str = (
        ", ".join(recent_entry_titles)
        if recent_entry_titles
        else "(no recent engagements)"
    )
    return (
        f"Propose approximately {target_count} papers.\n\n"
        f"User's current interests: {interests_str}\n\n"
        f"Recent papers and problems they've engaged with: {recent_str}"
    )
