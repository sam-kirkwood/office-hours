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
- **docs/orientation-and-calibration-design.md** — the reshape of onboarding + the daily loop into four intake signals (A/B/C/D), per-interest *paths*, an amended entry-point default, and the in-flight correction loop. **It amends `survey-and-difficulty-design.md` §1, §2.3, §2.7, §3.4, §3.5.** Read it before building anything in the survey / add-interest / entry-point / per-problem-controls area. **Status: Part A (the responsive daily loop) built — Phase 12 complete; Part B (conversational orientation) is Phase 13, next. Its design decisions are resolved (see its "Resolved decisions").**

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
2. **Python FastAPI on Railway/Fly** — all Claude API calls. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §Service topology for the full route tree. Headline routes: `/generate-problem`, `/parse-solution`, `/grade-solution`, `/generate-paper-engagement`, `/grade-paper-answer`, `/paper-question`, `/suggest-papers`, `/propose-papers`, `/ingest-paper-user`, `/surface-daily`, `/concept-review-resolve`, `/refresher-resolve`, `/generate-concept-brief`, `/generate-edge-description`, `/add-interest/{parse,resolve,rewrite-summaries}`, `/survey/suggest-interests`, `/assess-engagement`, `/plan-queue`, `/check-deferred`, `/run-daily-planner`, `/generate-curation-report`, `/compute-cross-pollination`, `/curiosity-box`.

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
- Problem pool: cache by `(topic_node_id, difficulty, intent)` (plus optional subtopic tag) so multiple users on the same topic can share problems. The `intent` axis (`teach` / `refresh` / `consolidate`) was added in Phase 10-rev §2f. Paper-tied problems (`paper_id IS NOT NULL`) are excluded from generic pool reuse.

## Key design constraints

- **Hints are pre-generated at problem creation time** and stored. Never generated on demand. Prevents drift and accidental answer leakage. Each hint carries a `part_label` (which part of a multi-part problem it addresses); the ProblemView renders it as a chip.
- **Problem statements follow a canonical template** (Phase 10.5-rev Step 3): historical context lives in `context_md` (rendered first, above the statement), the statement uses `## Setup` / `## The problem` headings and bold `**(a)**` parts (never `1.`/"Part 1"), display math for standalone equations. Enforced in the generation prompt; the render layer ([ProblemView.tsx](web/components/ProblemView.tsx), via remark-gfm) stays tolerant of older shapes. The one-off `scripts/reformat_problems.py` (Haiku) brings pre-template problems in line.
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

Dropped in [migration 20250016](supabase/migrations/20250016_drop_deprecated_tables.sql): `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`, `pending_topic_requests`. v1 plan-walking tables are gone from the schema.

## Build phases (revised)

The pivot plan lives in docs/pivot-plan.md with a status line. Sessions execute one phase-step at a time; commit after each.

1. Phases 1–3 (v1) and Phase 4 step 1: skeleton, curriculum seed, FastAPI scaffold, problem generation, solution upload + parsing. Largely complete.
2. Phase 4-rev — graph migration and queue foundation
3. Phase 5-rev — skill tree view + problem flow on new model
4. Phase 6-rev — paper engagement
5. Phase 7-rev — adaptation, refreshers, cross-pollination
6. Phase 8-rev — weekly curation and operator surfaces
7. Phase 9-rev — polish
8. Phase 10-rev — survey redesign, curriculum curator, queue UX, spirit gaps, skill-tree interaction, mobile polish, hardening (see [docs/phase-plans/phase-10-rev-plan.md](docs/phase-plans/phase-10-rev-plan.md)). **Done.**
9. Phase 10.5-rev — pre-launch remediation, the **operator-walkthrough round** (queue/refresher correctness, problem-page template, survey rendering, skill-tree/notebook polish; see [docs/phase-plans/phase-10.5-rev-plan.md](docs/phase-plans/phase-10.5-rev-plan.md)). **Done** — its remediation purpose is served. The remaining survey-copy / Stage-4 items were *not* patched in place; they were superseded by the design-review round below.
10. Phase 12 — **the responsive daily loop** (design-review round): card action set, the easier/harder/assume-less correction loop, the curiosity box as an intent router, steering. See [docs/orientation-and-calibration-design.md](docs/orientation-and-calibration-design.md) Part A + [phase-12 plan](docs/phase-plans/phase-12-responsive-daily-loop-plan.md). **Done.**
11. Phase 13 — **conversational orientation**: the four-signal tutor, rich per-interest paths, the §3.4 entry-point amendment, node-level calibration, the daily add-interest reshape. See orientation doc Part B + [phase-13 plan](docs/phase-plans/phase-13-conversational-orientation-plan.md). **Next.**
12. Phase 11-deploy — FastAPI deploy to Fly/Railway, pg_cron for the daily curator, Sentry, plus a reader-facing README. Keeps its original number but **runs last**, once the operator is happy (localhost is the dev/test loop until then). No longer launch-gated by 10.5.
13. Deferred (v2.1+): live arXiv search, bespoke megagraph viz, calendar view, BYO API key, notebook export, etc.

The launch-gating framing (🔴/🟡, soft launch) is retired: the app is finished before it is released. Do not start a phase before the prior phase is committed and the pivot plan's status line is updated.

## Design principles

Established in the design-system session (May 2026). These govern all future UI work.

### Aesthetic intent

Clean and academic but slightly cosy — closer to a well-made university press book or a quiet study than a SaaS dashboard. Not gamified, not slick, not generic-AI-startup. Warmth comes from colour temperature, the serif, and spacing — not from gradients, glassmorphism, heavy shadows, or decorative illustration.

### Colour tokens

| Token | Value | Role |
|---|---|---|
| `--background` | `#FAF7F0` | Paper-like off-white. All page backgrounds. |
| `--foreground` | `#1C1917` | Warm near-black. All body text. |
| `--amber` / `--primary` | `#B8860B` | Honey amber — bee-themed primary accent. Interactive elements, active states, focus rings, problem-mode colour. Used sparingly. |
| `--forest` / `--secondary` | `#4A7066` | Muted forest — secondary accent. Paper-mode colour, nav structural elements, secondary actions. |
| `--amber-subtle` | oklch(0.958 0.025 82) | Very light amber wash for highlight backgrounds. |
| `--forest-subtle` | oklch(0.945 0.020 170) | Very light forest wash for paper-mode card tints. |
| `--muted` / `--muted-foreground` | warm grays | Secondary text and muted surfaces. |

Dark mode is **not** a design priority for v2. The `.dark` tokens in `globals.css` are kept structurally valid so shadcn compiles, but are untested.

### Typography

| Role | Font | Tailwind class |
|---|---|---|
| UI chrome (nav, labels, buttons, metadata) | Inter | `font-sans` (default) |
| Reading surfaces (problem statements, paper context, notebook entries, node detail text) | Lora | `font-serif` |
| Equations and code | JetBrains Mono | `font-mono` |

- Source Serif 4 is loaded as `font-source-serif` for the `/design` font comparison page only. Do not use it on production surfaces.
- Reading body: `text-base leading-[1.7] font-serif`. Max reading width: `max-w-prose` (~65 ch).
- Section labels / nav: `text-xs font-semibold uppercase tracking-widest text-muted-foreground`.
- Never use Geist (removed from this project).

### Density and spacing

- Border radius: `--radius: 0.375rem` (6px). Restrained, not rounded or bubble-like.
- Reading columns: constrained to `max-w-prose` or `max-w-3xl` for full layouts.
- Generous vertical rhythm between sections (`space-y-6` inside sections, `py-10` between).
- Line height: `leading-[1.7]` for serif reading surfaces, `leading-relaxed` for UI text.

### Restraint rules

- No gradients. No glassmorphism. No heavy box-shadows. No decorative illustration.
- No streaks, badges, or gamification UI — enforced at the product level, reinforce at the design level.
- Accent colours used sparingly: amber for interactive affordances and problem-mode; forest for paper-mode and structural nav. Not scattered decoratively.
- The `/design` route is the regression reference. Check it when applying styles to new surfaces.

### Motion tokens

Defined in `globals.css` as CSS variables. Apply via arbitrary Tailwind values:
`transition-colors duration-[var(--duration-fast)] [transition-timing-function:var(--ease-productive)]`

| Token | Value | Use for |
|---|---|---|
| `--duration-fast` | 100ms | Hover state colour changes, icon toggles |
| `--duration-standard` | 200ms | Panel open/close, tab switches, accordion expand |
| `--duration-slow` | 350ms | Page transitions, large layout shifts |
| `--ease-productive` | `cubic-bezier(0, 0, 0.2, 1)` | UI responses — snappy ease-out |
| `--ease-expressive` | `cubic-bezier(0.4, 0, 0.2, 1)` | Content entries — balanced ease-in-out |

Do not animate anything that hasn't been explicitly designed. These tokens exist so when animation is added it uses a consistent vocabulary.

### Queue badge colour semantics

The daily queue uses shadcn `Badge` variants to signal item kind. These are fixed — don't change them without a design decision:

| Kind | Badge | Rationale |
|---|---|---|
| `problem` | `variant="default"` (amber filled) | Active work — primary amber |
| `paper_engagement` | `variant="secondary"` (forest filled) | Reading — primary forest |
| `refresher` | `variant="outline"` + forest border/text | Revisiting known material — same family as paper |
| `suggested_interest` | `variant="ghost"` (neutral grey) | Soft suggestion, not a commitment |

### Skill tree node style

Nodes in `SkillTreeView` use `rounded-full` circles (exception to the 6px radius rule — the circular shape reads as organic/conceptual rather than UI chrome). Node text uses `font-serif`. User nodes are 130×130px; adjacent/suggested nodes are 108×108px. State is conveyed by border weight and tint:

- Unseen: `border-border bg-card`
- Active: `border-2 border-primary bg-amber-subtle`
- Comfortable: `border-[forest]/50 bg-forest-subtle`
- Bookmarked: `border-amber/50 bg-amber-subtle`
- Struggling: `border-destructive/30 bg-destructive/[0.07]`
- Adjacent (suggested): dashed `border-border/50 bg-background`, muted serif text

A legend panel is rendered absolutely in the bottom-left of the canvas.

### Component library

shadcn/ui (radix-nova style) with Tailwind v4. Components live in `web/components/ui/`. The design-system page at `/design` shows every component in context. Check it before adding new UI patterns.

---

## Working rules

- Read SPEC.md, ARCHITECTURE.md, docs/graph-design.md, docs/personas.md, and docs/pivot-plan.md at the start of any significant session.
- Use plan mode (Shift+Tab) for any session that will touch multiple files. Show the plan and stop for review before writing code.
- When the docs and existing code conflict, surface the conflict and propose a resolution — don't pick one silently.
- Sessions end at natural review boundaries (a working migration, a passing test, a deployable feature). Not mid-feature.
- Commit at the end of every working session. Update docs/pivot-plan.md's status line.
- Costs matter. Long sessions with growing context are expensive; prefer focused sessions with tight scope.