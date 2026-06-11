"""One-off: normalise existing problems to the Phase 10.5-rev Step 3 template.

The problem generator now pins a canonical statement template (context-first,
`## Setup` / `## The problem` headings, bold `**(a)**` parts, display math,
valid GFM tables) and emits a per-hint `part_label`. That only governs *new*
problems — the ~two dozen already in the pool predate it and vary wildly in
structure (some `(a)`, some `1.`, some "Part 1"; context buried in the
statement; no hint→part labels).

This script asks Haiku to *reformat* each existing problem to the template
WITHOUT changing its content — same physics, same numbers, same parts, same
difficulty — and to assign a `part_label` to each existing hint. Problems are
normally immutable once attempted; the operator has authorised deleting the
handful of test attempts so the rewrite is clean (only on --apply, and only
for problems that actually change).

Usage:
    uv run --project api python scripts/reformat_problems.py --dry-run
    uv run --project api python scripts/reformat_problems.py --dry-run --id <uuid>
    uv run --project api python scripts/reformat_problems.py --apply

Prereq: migration 20250032 (problem_hints.part_label) applied.
Env: ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SECRET_KEY from api/.env or env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"


def _load_dotenv_into_environ(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key not in os.environ:
            os.environ[key] = val.strip().strip("'\"")


# Load env and put the api package on the path so we can reuse the logged
# call_json + the shared clients (every Claude call lands in llm_calls).
_load_dotenv_into_environ(API_DIR / ".env")
sys.path.insert(0, str(API_DIR))

from anthropic_client import call_json, get_anthropic_client  # noqa: E402
from config import HAIKU_MODEL, SONNET_MODEL  # noqa: E402
from supabase_client import get_supabase_client  # noqa: E402


# ---------------------------------------------------------------------------
# LLM contract
# ---------------------------------------------------------------------------


class ReformattedProblem(BaseModel):
    """What Haiku returns for one problem. `hint_part_labels` is aligned to the
    problem's hints in ascending level order — one label per hint."""

    statement_md: str
    context_md: str | None = None
    hint_part_labels: list[str]


SYSTEM_PROMPT = """You reformat existing science problems to a fixed house \
template. You are NOT rewriting or improving the problem — preserve its \
content exactly: the same physics, the same setup, the same numbers and \
symbols, the same parts in the same order, the same difficulty. Change only \
presentation and structure.

Apply this template to the statement:

1. Historical / biographical framing (dates, "In 1858 Cayley…", named-scientist \
stories) must NOT live in the statement. If the statement opens with such \
context, MOVE it into context_md verbatim (merging with any existing \
context_md). The statement opens with at most one plain sentence framing what \
the problem is about.
2. Definitions, notation, or apparatus the solver must use go under a Markdown \
heading "## Setup". Do not add or remove any — only relocate what is already \
there.
3. The questions go under a Markdown heading "## The problem".
4. Every part is labelled with a bold parenthesised letter in order: "**(a)**", \
"**(b)**", "**(c)**", … Convert any other scheme ("1.", "Part 1", "(i)") to \
this, preserving order and content. A single-part problem keeps no part label.
5. Standalone equations use display math "$$ … $$" on their own line with a \
blank line either side; short in-sentence expressions stay inline "$ … $". Do \
not change any equation's content.
6. Tabular data must be a valid GitHub-flavoured Markdown table (header row \
then a "|---|---|" separator). Fix malformed tables; do not change their data.

Then assign each hint a part_label naming the part(s) it addresses, using the \
SAME labels as the reformatted statement: "Part (c)", "Parts (a)–(b)", or \
"Whole problem" for hints that apply throughout (typically the first one or \
two ladder rungs). For a single-part problem every label is "Whole problem". \
Return one label per hint, in the order given.

Return a single JSON object, no prose, no markdown fences, with keys: \
"statement_md" (string), "context_md" (string or null), "hint_part_labels" \
(array of strings, exactly one per hint in order)."""


def build_user_prompt(
    *, statement_md: str, context_md: str | None, hints: list[str]
) -> str:
    hints_block = "\n".join(f"{i + 1}. {h}" for i, h in enumerate(hints))
    return (
        f"EXISTING context_md (may be null):\n{context_md or '(null)'}\n\n"
        f"EXISTING statement_md:\n{statement_md}\n\n"
        f"EXISTING hints ({len(hints)}, in level order):\n{hints_block}\n\n"
        f"Reformat to the template and return one part_label per hint "
        f"(exactly {len(hints)} labels, in order)."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _short(s: str, n: int = 280) -> str:
    s = s.replace("\n", " ⏎ ")
    return s if len(s) <= n else s[:n] + "…"


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="print changes, write nothing (default)")
    g.add_argument("--apply", action="store_true", help="write changes + delete attempts on rewritten problems")
    ap.add_argument("--id", help="reformat only this problem id (for spot-checking)")
    ap.add_argument("--limit", type=int, help="cap the number of problems processed")
    ap.add_argument("--model", default=HAIKU_MODEL, help=f"model id (default {HAIKU_MODEL}; pass {SONNET_MODEL} for higher fidelity)")
    args = ap.parse_args()
    apply = args.apply  # dry-run is the default when neither flag is set

    supabase = get_supabase_client()
    anthropic = get_anthropic_client()

    q = supabase.table("problems").select("id, title, statement_md, context_md")
    if args.id:
        q = q.eq("id", args.id)
    q = q.order("created_at")
    problems = q.execute().data or []
    if args.limit is not None:
        problems = problems[: args.limit]

    print(f"{'APPLY' if apply else 'DRY-RUN'} · {len(problems)} problem(s) · model={args.model}\n")

    changed = 0
    skipped = 0
    for p in problems:
        pid = p["id"]
        hints_resp = (
            supabase.table("problem_hints")
            .select("id, level, text")
            .eq("problem_id", pid)
            .order("level")
            .execute()
        )
        hint_rows = hints_resp.data or []
        hint_texts = [h["text"] for h in hint_rows]

        try:
            result = call_json(
                client=anthropic,
                supabase=supabase,
                model=args.model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=build_user_prompt(
                    statement_md=p["statement_md"],
                    context_md=p.get("context_md"),
                    hints=hint_texts,
                ),
                schema=ReformattedProblem,
                route="/reformat-problem",
                request_summary={"problem_id": pid},
                max_tokens=8192,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"✗ {pid} — LLM/parse error, skipped: {exc}\n")
            skipped += 1
            continue

        # Guards: label count must match; reformat must not have dropped the
        # bulk of the statement (a crude content-loss tripwire).
        if len(result.hint_part_labels) != len(hint_rows):
            print(
                f"✗ {pid} — got {len(result.hint_part_labels)} labels for "
                f"{len(hint_rows)} hints, skipped\n"
            )
            skipped += 1
            continue
        if len(result.statement_md) < 0.6 * len(p["statement_md"]):
            print(
                f"✗ {pid} — reformatted statement is much shorter "
                f"({len(result.statement_md)} vs {len(p['statement_md'])} chars), "
                f"likely dropped content; skipped\n"
            )
            skipped += 1
            continue

        print(f"● {p.get('title') or pid}  [{pid}]")
        print(f"    statement: {_short(result.statement_md)}")
        if result.context_md and not p.get("context_md"):
            print(f"    context  : (new) {_short(result.context_md)}")
        print(f"    labels   : {result.hint_part_labels}")

        if apply:
            supabase.table("problems").update(
                {"statement_md": result.statement_md, "context_md": result.context_md}
            ).eq("id", pid).execute()
            for row, label in zip(hint_rows, result.hint_part_labels):
                supabase.table("problem_hints").update({"part_label": label}).eq(
                    "id", row["id"]
                ).execute()
            # Problems are immutable once attempted; clear the (test) attempts on
            # this rewritten problem so the invariant holds. Operator-authorised.
            deleted = (
                supabase.table("attempts").delete().eq("problem_id", pid).execute()
            )
            n_del = len(deleted.data or [])
            if n_del:
                print(f"    deleted  : {n_del} attempt(s)")
        print()
        changed += 1

    print(
        f"\n{'Wrote' if apply else 'Would write'} {changed} problem(s); skipped {skipped}."
    )
    if not apply and changed:
        print("Re-run with --apply to persist. (Spot-check a few with --id first.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
