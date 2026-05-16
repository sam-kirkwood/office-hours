# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: this project is mid-pivot

The product was redesigned. The current source of truth is:

- **SPEC.md** — user-facing behavior (v2)
- **ARCHITECTURE.md** — technical structure (v2)
- **docs/graph-design.md** — the megagraph model (new)
- **docs/personas.md** — three personas; the primary design tool. Check feature decisions against these.
- **docs/archive/SPEC-v1.md** and **docs/archive/ARCHITECTURE-v1.md** — prior versions, for context only. Do not use as design guidance.
- **docs/pivot-plan.md** — the working plan for the pivot work. Status line at the top tracks progress.

When the docs and the existing code disagree, the docs are right. The code is being brought in line with them via the pivot plan.

## Project overview

A private personalized science tutor for working professionals (~10–30 trusted friends, hard cap 30). Users state interests in free text; the system builds an evolving queue of problems and paper engagements that match what they actually want to learn. Pen-and-paper solutions are photographed and submitted; everything accumulates into the user's LaTeX notebook. The interests across users form a shared knowledge graph (the megagraph) that surfaces nearby topics for discovery.

## Core philosophy (from SPEC.md)

These are constraints on feature decisions, not slogans. When in doubt, defer to these:

- No guilt, no streaks. The product is here when the user wants it.
- Working professionals are competent. Don't gate, don't condescend.
- Pen and paper is the medium.
- Hints help; they don't solve.
- Feedback is dialogic, not graded.
- The notebook is the artefact.
- The system curates; the user trusts.
- Time is not a commitment — never ask users to budget time.
- The graph is shared and grows with use.

## Architecture

Two services:

1. **Next.js on Vercel** — frontend + web API routes. Auth, CRUD, signed upload URLs, queue surfacing. Calls the Python service for all AI operations.
2. **Python FastAPI on Railway/Fly** — all Claude API calls. Routes include `/generate-problem`, `/parse-solution`, `/grade-solution`, `/generate-paper-engagement`, `/grade-paper-answer`, `/paper-question`, `/suggest-papers`, `/add-interest`, `/update-queue`, `/generate-curation-report`, `/compute-cross-pollination`.

Shared infrastructure: Postgres (Supabase), Supabase Auth (email magic links), Supabase Storage (handwritten solution images).

## Next.js 16 notes

- Route protection lives in `web/proxy.ts` (not `middleware.ts` — renamed in Next.js 16). The exported function is named `proxy`, not `middleware`.
- Tailwind v4 uses `@import "tailwindcss"` in CSS, not `@tailwind` directives.
- `web/` has its own `.git` repo initialized by `create-next-app`.

## Commands

All Next.js commands run from `web/`:

```bash
npm run dev        # local dev server (localhost:3000)
npm run build      # production build
npm run lint       # ESLint
```

Python FastAPI commands run from `api/` (requires uv):

```bash
uv sync                          # install runtime + dev deps
uv run uvicorn main:app --reload # local dev server (localhost:8000)
uv run pytest                    # tests
```

Both services need each side of the shared bearer token. In dev: set `INTERNAL_API_TOKEN` to the same value in `web/.env.local` and `api/.env`, and set `PYTHON_API_URL=http://localhost:8000` in `web/.env.local`.

Apply DB migrations (from repo root):

```bash
npx supabase db push --db-url <your-supabase-db-url>
```

## LLM usage

- **Sonnet 4.6**: problem generation, paper engagement generation, grading, dialogic feedback, vision parsing, new-interest node generation, weekly curation reports.
- **Haiku**: deduplication checks, cheap classification, routing decisions.
- Every Claude call must be logged to the `llm_calls` table (route, model, input/output tokens, estimated cost, optional user_id).
- Problem pool: cache by `(topic_node_id, difficulty)` so multiple users on the same topic can share problems. Paper-tied problems (`paper_id IS NOT NULL`) are excluded from generic pool reuse.

## Key design constraints

- **Hints are pre-generated at problem creation time** and stored. Never generated on demand. Prevents drift and accidental answer leakage.
- **Paper engagement questions are pre-generated** when the paper enters a user's queue, for the same reason.
- **Vision parse is always user-reviewed** before grading. UI must show rendered markdown+LaTeX the user can edit inline.
- **Original images are always retained** even if parsing fails.
- **Problems are immutable once attempted**. Edits create a new `version` row with `previous_version_id` set.
- **Disputed grades are queued for operator review** — no automated re-grading in v1.
- **Interest deduplication is autonomous.** Claude's dedup decisions are not user-confirmed. The operator catches mistakes in weekly curation.
- **Cross-pollination is gated.** Suggested interests don't surface until after the first weekly curation round.
- **No streaks, badges, or social mechanics.** This is a deliberate constraint, not a missing feature.
- **No scale engineering.** Hard cap of 30 users. Queries can load the whole megagraph; the dedup candidate set can be bounded by a simple title-similarity filter.

## Database schema highlights

All tables use UUID PKs and timestamps. Key tables (see ARCHITECTURE.md for full data model):

- `users`, `surveys` — onboarding
- `nodes`, `edges` — unified graph of foundation + interest nodes
- `user_interests`, `user_node_states` — per-user graph state
- `queue_items`, `surfaced_picks` — the queue and what's been surfaced
- `problems`, `problem_hints`, `context_hooks` — problem content
- `papers`, `paper_engagements`, `paper_answers`, `paper_qa` — paper content
- `attempts` — user work on problems
- `notebook_entries` — long-term record of attempts and engagements
- `bookmarks`, `refresher_schedule` — user state
- `curation_proposals`, `megagraph_snapshots` — operator curation
- `llm_calls` — cost observability

Deprecated (kept briefly for migration, no new writes): `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`.

## Build phases (revised)

The pivot plan lives in docs/pivot-plan.md with a status line. Sessions execute one phase-step at a time; commit after each.

1. Phases 1–3 (v1) and Phase 4 step 1: skeleton, curriculum seed, FastAPI scaffold, problem generation, solution upload + parsing. Largely complete.
2. Phase 4-rev — graph migration and queue foundation
3. Phase 5-rev — skill tree view + problem flow on new model
4. Phase 6-rev — paper engagement
5. Phase 7-rev — adaptation, refreshers, cross-pollination
6. Phase 8-rev — weekly curation and operator surfaces
7. Phase 9-rev — polish
8. Deferred (v2.1+): live arXiv search, bespoke megagraph viz, calendar view, BYO API key, notebook export, etc.

Do not start a phase before the prior phase is committed and the pivot plan's status line is updated.

## Working rules

- Read SPEC.md, ARCHITECTURE.md, docs/graph-design.md, docs/personas.md, and docs/pivot-plan.md at the start of any significant session.
- Use plan mode (Shift+Tab) for any session that will touch multiple files. Show the plan and stop for review before writing code.
- When the docs and existing code conflict, surface the conflict and propose a resolution — don't pick one silently.
- Sessions end at natural review boundaries (a working migration, a passing test, a deployable feature). Not mid-feature.
- Commit at the end of every working session. Update docs/pivot-plan.md's status line.
- Costs matter. Long sessions with growing context are expensive; prefer focused sessions with tight scope.