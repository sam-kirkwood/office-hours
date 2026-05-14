# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A private personalized science tutor for ~10–30 trusted friends. Users get a tailored learning plan, a daily math/physics problem with historical context, handwritten solution submission with AI vision parsing, automated grading, and adaptive plan updates. See SPEC.md and ARCHITECTURE.md for full detail.

## Next.js 16 notes

- Route protection lives in `web/proxy.ts` (not `middleware.ts` — renamed in Next.js 16). The exported function is named `proxy`, not `middleware`.
- Tailwind v4 uses `@import "tailwindcss"` in CSS, not `@tailwind` directives.
- `web/` has its own `.git` repo initialized by `create-next-app`.

## Architecture

Two services:

1. **Next.js on Vercel** — frontend + web API routes. Handles auth, CRUD, signed upload URLs. Stateless; calls the Python service for all AI operations.
2. **Python FastAPI on Railway/Fly** — all Claude API calls. Routes: `POST /generate-plan`, `/generate-problem`, `/parse-solution`, `/grade-solution`, `/update-plan`.

Shared infrastructure: Postgres (Neon or Supabase), Supabase Auth (email magic links), Supabase Storage (handwritten solution images).

## Commands

All Next.js commands run from `web/`:

```bash
npm run dev        # local dev server (localhost:3000)
npm run build      # production build
npm run lint       # ESLint
```

Python FastAPI commands run from `api/` (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv sync                          # install runtime + dev deps
uv run uvicorn main:app --reload # local dev server (localhost:8000)
uv run pytest                    # tests
```

Both services need each side of the shared bearer token. In dev: set
`INTERNAL_API_TOKEN` to the same value in `web/.env.local` and `api/.env`, and
set `PYTHON_API_URL=http://localhost:8000` in `web/.env.local`.

Apply DB migrations (from repo root):

```bash
npx supabase db push --db-url <your-supabase-db-url>
```

## LLM usage

- **Sonnet 4.6**: problem generation, grading, vision parsing (handwritten math → markdown+LaTeX)
- **Haiku**: cheap classification and routing (e.g., categorizing pending topic requests)
- Every Claude call must be logged to the `llm_calls` table (route, model, input/output tokens, estimated cost)
- Cache problem generation by `(canonical_topic_id, difficulty, context_hook_id)` so multiple users on the same topic share problems

## Key design constraints

- **Hints are pre-generated at problem creation time** and stored — never generated on demand. Prevents drift and accidental answer leakage.
- **Vision parse is always user-reviewed** before grading. The UI must show a rendered markdown+LaTeX preview the user can edit inline.
- **Original images are always retained** even if parsing fails.
- **Disputed grades are queued for operator review** — no automated re-grading in v1.
- **Pending topic requests** (from user surveys) go through operator approval before entering `canonical_topics`.

## Database schema highlights

All tables use UUID PKs and timestamps. Key tables:
- `users`, `surveys` — onboarding
- `canonical_topics`, `canonical_edges` — curated curriculum graph
- `pending_topic_requests` — user-requested topics awaiting operator approval
- `user_plans`, `plan_nodes` — per-user ordered paths through the graph
- `problems`, `problem_hints`, `context_hooks` — generated content
- `daily_assignments`, `attempts` — user work and grades
- `llm_calls` — cost observability

## Build phases

1. Skeleton (mocked content, no AI)
2. Curriculum + survey + plan review (visual skill tree)
3. Problem generation + hints (Python service live)
4. Vision parsing + review UI
5. Grading + feedback + plan adaptation
6. Cost dashboard + polish → v1 ships
7+ Deferred: paper-reading days, annotated notebook, dynamic hints, BYO API key

Do not implement phase 7+ features until phases 1–6 are complete.
