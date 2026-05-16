# Phase 3 — execution notes

Working notes for the multi-session Phase 3 build. Source-of-truth for the
product is still [SPEC.md](../SPEC.md) and [ARCHITECTURE.md](../ARCHITECTURE.md);
this file just captures the *execution* decisions and current state.

## Where we are

- **Phase 1**: done (skeleton, mocked daily problem, photo upload to Supabase
  Storage).
- **Phase 2**: done (curriculum graph seeded, survey, plan-review UI, plan
  approval).
- **Phase 3**: **done**. All 8 steps shipped and live-smoke-tested against
  real Anthropic + Supabase APIs on 2026-05-14. Step 7 (difficulty helper)
  was folded into step 4; step 8 (docs) was folded into step 6. The full
  loop works: an authenticated user with an active plan opens
  [/daily](../web/app/daily/page.tsx) and gets an AI-generated problem with
  hints and historical context.

## Phase 3 goal

When an authenticated user with an approved plan opens
[/daily](../web/app/daily/page.tsx), they see a real AI-generated problem
(statement + canonical solution + rubric + 5 stored hints + a 2–4 paragraph
historical context block) drawn from the next node in their plan. Every Claude
call is logged to `llm_calls` for cost observability. No vision parsing, no
grading, no plan adaptation — those are Phases 4 and 5.

## Decisions locked in for Phase 3

| Decision | Choice | Why |
|---|---|---|
| Python service hosting | **Local-only** for now | Faster iteration on prompts; deploy to Railway/Fly is deferred to Phase 6 polish. |
| Daily problem trigger | **On-demand on first visit** | Simpler than cron; tolerable latency for ~10 users; problem cache means most generations are free. |
| Problem sharing | **Shared across users** by `(canonical_topic_id, difficulty, context_hook_id)` cache key | Per ARCHITECTURE.md §Cost controls. No per-user struggle-signal personalisation in Phase 3 — struggle signals arrive with grading in Phase 5. |
| Internal auth between Next.js and Python | Shared bearer token `INTERNAL_API_TOKEN` | Trusted user base, no need for mTLS; single env var on each side. |
| Difficulty selection | Deterministic from `surveys.difficulty_curve` × topic difficulty band | See table below. Adaptive selection lands in Phase 5. |

## Step status

| # | Step | Status |
|---|---|---|
| 1 | DB migration `20250005_phase3_schema.sql` | **Done, applied** |
| 2 | Seed `02_context_hooks.sql` (31 hooks) | **Done, applied** |
| 3 | Python FastAPI scaffolding at `api/` | **Done** |
| 4 | `POST /generate-problem` end-to-end | **Done + live-tested**. Bug-fix follow-up: added `generated_context_md` column (migration 20250006). |
| 5 | Hook matching (Haiku classification) | **Done + live-tested**. Bug-fix follow-up: `temperature=0` on Haiku to keep cache key stable. |
| 6 | Next.js wiring: `ensureTodaysAssignment`, markdown+LaTeX render, real `/daily` | **Done + live-tested** (2026-05-14). Step 8 bundled in. |
| 7 | Difficulty mapping helper | **Done** (`api/difficulty.py`, folded into step 4) |
| 8 | Docs touch-ups (root CLAUDE.md `Commands`, `.env.local.example`) | **Done** (folded into step 6 diff) |

## Handoff to Phase 4

Phase 3 is closed. The next phase is **Phase 4 — vision parsing + review UI**
(ARCHITECTURE.md §Build phases). Pre-existing scope: stand up
`POST /parse-solution` in the Python service, replace the mocked submit on
[../web/app/upload/page.tsx](../web/app/upload/page.tsx) with a real call
through Next.js, and build the editable markdown+LaTeX review UI before the
parsed output goes anywhere near grading (which is Phase 5).

### Open follow-ups carried out of Phase 3

Small, deliberate debts left behind so Phase 4 picks them up with context:

1. **`daily_assignments` day-key uses *server-local* TZ**
   ([../web/lib/dailyAssignment.ts](../web/lib/dailyAssignment.ts)
   `todayKey()`). Fine for an SF-based operator + friends, breaks for a
   Tokyo user. Fix when needed: store `timezone` on `profiles`, set it from
   the browser on first visit, plumb it into `todayKey()`.
2. **`prose` Tailwind classes are dead weight.** The daily page and
   [../web/lib/markdown.tsx](../web/lib/markdown.tsx) sprinkle
   `prose prose-zinc` etc., but `@tailwindcss/typography` is not installed.
   Markdown still renders (semantic HTML), just without article-style
   margins. Either install the plugin or drop the classes — Phase 4's review
   UI will want the styling, so installing is the cleaner call.
3. **Hint inline rendering looks awkward.** Each hint runs through
   `<MarkdownLatex>` which wraps in a `<div>` inside an `<li>`. Visually OK
   but block-inside-inline. Swap to a plain-text render or build a
   "markdown-as-span" component if hints rarely use heavy math.
4. **Race-loss path on `daily_assignments` insert is untested live.**
   `isUniqueViolation()` exists ([../web/lib/dailyAssignment.ts](../web/lib/dailyAssignment.ts))
   but has never fired. Same status as the matching path in
   [../api/routes/generate_problem.py](../api/routes/generate_problem.py).
   Both can wait for the first time real concurrent traffic actually hits.
5. **One-problem-per-day is a hard gate.** `unique (user_id, assigned_for_date)`
   on `daily_assignments` blocks bonus problems. Operator wants this opened
   up post-v1; likely shape is a separate `bonus_assignments` table so the
   "today's canonical problem" semantic stays clean. Don't paint into a
   corner.

### What live-tested means for Phase 3

Ran the full loop against real Anthropic + real Supabase on 2026-05-14:
- `POST /generate-problem` Python side: cache hit / miss, llm_calls rows
  with sane token counts and USD cost, found and patched two bugs
  (`generated_context_md` schema gap; Haiku non-determinism flipping the
  cache key).
- Next.js `/daily` end-to-end: cold gen → loading skeleton → rendered
  problem with context + hints. Refresh in same day reuses the assignment
  (no Python call). Rendered markdown + LaTeX both via curated hook
  `summary_md` and via Sonnet's `generated_context_md`.

The only untested-live bits are the two race-loss paths above.

## Step 1 — DB migration details

File: [supabase/migrations/20250005_phase3_schema.sql](../supabase/migrations/20250005_phase3_schema.sql)

Key shape decisions worth not re-litigating:

- **`llm_calls` includes cache-read/write token columns** even though Phase 6
  is what surfaces them. Adding now avoids a follow-up migration once prompt
  caching is wired in step 4.
- **Two partial unique indexes** make the `(topic, difficulty, hook)` cache
  key race-safe across the hook-present and hook-absent cases. Lets us write
  `insert ... on conflict do nothing` then re-select, no advisory locks.
- **`problems` SELECT policy tightened**: was `auth.role() = 'authenticated'`,
  now scoped to "you have an assignment for this problem". Otherwise users
  could read `solution_md` / `rubric_md` for problems they hadn't been served.
  Service role bypasses RLS so the Python service and server-side Next.js
  helpers are unaffected.
- **`problem_hints` SELECT policy mirrors problems** (only visible via an
  assignment). `llm_calls` has no SELECT policy at all — only service role.
- **`plan_node_id` on `daily_assignments`**: Phase 5's plan adaptation needs
  to know which node an attempt advanced. Adding it now is one line; backfilling
  later would be annoying.

## Step 2 — Context hooks seed details

File: [supabase/seed/02_context_hooks.sql](../supabase/seed/02_context_hooks.sql)

- 31 hooks. Every canonical topic from
  [01_curriculum.sql](../supabase/seed/01_curriculum.sql) is hit by at least
  one hook.
- `summary_md` is a 2–3 sentence seed. The problem generator (step 4) expands
  it into the 2–4 paragraph context block on the daily page.
- `sources_json` stores `{title, author, year}` only. URLs are deliberately
  not fabricated — operator can paste them in via the Phase 6 hooks editor.
- Tagged dollar quotes (`$t$`, `$ctx$`, `$src$`) avoid apostrophe escaping.
- Re-runnable: `on conflict (slug) do update set ...` updates title, summary,
  topic links, difficulty, and sources.

## Step 3 — Python service scaffolding

Target layout at repo root:

```
api/
  pyproject.toml          # uv-installable, pin Python 3.12+
  main.py                 # FastAPI app: /healthz + route mounts
  routes/
    generate_problem.py
  prompts/
    problem.py            # system + user prompt builders for Sonnet
    hook_match.py         # Haiku hook-matching prompt
  anthropic_client.py     # wrapper that ALWAYS logs to llm_calls
  supabase_client.py      # service-role client
  schemas.py              # pydantic request/response models
  config.py               # env loading
  tests/
    test_generate_problem.py    # mocked anthropic client
    test_cache_lookup.py
  .env.example
  README.md
```

Conventions to follow:

- Anthropic SDK: use `claude-sonnet-4-6` for generation, `claude-haiku-4-5-20251001`
  for hook matching. Both with prompt caching on the system prompt (cf. the
  claude-api skill — apps built with it should include prompt caching).
- Every call routed through `anthropic_client.py`, which writes the
  `llm_calls` row before returning. No bypassing.
- Structured output via JSON mode + strict pydantic parse. Retry once with a
  tightened prompt on parse failure; log both attempts.
- Internal auth: FastAPI dependency that checks `Authorization: Bearer
  $INTERNAL_API_TOKEN` and 401s otherwise.

## Step 4 — `POST /generate-problem` flow

Request body: `{ user_id: uuid, plan_node_id: uuid }`.

1. Service-role SELECT on `plan_nodes` join `canonical_topics` to get topic +
   subtopics.
2. SELECT on `surveys` to get `difficulty_curve` for this user.
3. Compute difficulty per the table below.
4. SELECT context hooks tagged to this topic (`related_topic_ids` GIN index).
   If 0 hooks, hook_id = null (Claude will write context inline). If ≥ 1, call
   Haiku to pick best fit or "none".
5. **Cache check**: SELECT from `problems` where
   `(canonical_topic_id, difficulty, context_hook_id)` matches. If hit → return
   the existing problem id, skip the Sonnet call.
6. Sonnet generation. Strict JSON response: `statement_md`, `solution_md`,
   `rubric_md`, `hints` (array of 5 strings, levels 1–5), plus
   `generated_context_md` if no hook was matched.
7. Insert `problems` with `on conflict (canonical_topic_id, difficulty,
   context_hook_id) do nothing`, then re-select (race-safe).
8. Insert 5 `problem_hints` rows.
9. Return `{ problem_id }`. The Next.js caller is responsible for the
   `daily_assignments` row.

### Step 4 — what shipped

Implementation matches the flow above. Notes worth not re-litigating:

> **Follow-up fix (2026-05-14, mid-smoke-test):** the original step 4 dropped
> `generated_context_md` on insert — the column existed in the
> `GeneratedProblem` pydantic schema but had never been added to the
> `problems` table, and the route built its insert dict without that key. Fix
> shipped as migration
> [supabase/migrations/20250006_problems_generated_context.sql](../supabase/migrations/20250006_problems_generated_context.sql)
> + a one-line addition to the route insert + a round-trip assertion in
> `test_happy_path_generates_problem_and_hints`. The pre-fix smoke test still
> returned a usable `problem_id` for hook-matched topics; only the no-hook
> path was silently losing the context block.

- **Pricing constants** for `estimated_cost_usd` live in `PRICING` in
  [../api/anthropic_client.py](../api/anthropic_client.py) (confirmed with
  the operator 2026-05-14): Sonnet 4.6 — $3 / $15 / $0.30 / $3.75 per 1M
  (in / out / cache-read / cache-write); Haiku 4.5 — $1 / $5 / $0.10 / $1.25.
- **`call_json`** is a generic helper (`call_json[T: BaseModel]`) that adds
  prompt caching on the system block, parses JSON, validates against the
  pydantic schema, retries once on parse failure with a tightened user
  message, and logs every API call (including the failed first attempt) to
  `llm_calls`. Reused for Haiku in step 5.
- **Race-safe insert** is a try/except on `_is_unique_violation` rather than
  `on conflict do nothing` because supabase-py doesn't cleanly expose partial-
  index ON CONFLICT targets. The exception matcher checks `exc.code` for
  `'23505'` and string-matches "duplicate key" as a fallback. **Has never
  been hit against the real DB** — the test uses a synthetic exception with
  `code = '23505'`. Worth a live smoke test before step 6 wiring.
- **Hook selection is currently `pick_hook_stub`** in
  [../api/routes/generate_problem.py](../api/routes/generate_problem.py):
  first hook whose `difficulty_band` matches the topic's band, else null.
  Step 5 replaces it; the route shape doesn't change.
- **Auth dep** is [../api/auth.py](../api/auth.py):
  `require_internal_token` compares the `Authorization` header against
  `INTERNAL_API_TOKEN` from settings.
- **Difficulty helper** ([../api/difficulty.py](../api/difficulty.py)) was
  written now rather than deferred to step 7 — it's ~10 lines and step 4
  needs it anyway.
- **Tests** use `app.dependency_overrides` to inject `FakeSupabase` /
  `FakeAnthropic` chain-recording stubs (in
  [../api/tests/fake_supabase.py](../api/tests/fake_supabase.py) and
  [../api/tests/fake_anthropic.py](../api/tests/fake_anthropic.py)). Tests
  cover: auth (401), missing plan_node / survey (404), cache hit (no LLM
  call), happy path (5 hints written), retry on parse failure (both
  attempts logged), race-lost (re-select returns existing row), hook-summary
  plumbing into the user prompt. 27/27 pass; `ruff check` clean.

## Step 5 — Hook matching

Haiku prompt: given a topic title + description and a shortlist of up to ~6
candidate hooks (title + summary_md), return either `{ "hook_slug": "..." }`
or `{ "hook_slug": null, "reason": "..." }`. Strict JSON. Logged to
`llm_calls` like any other call.

### Step 5 — what shipped

> **Follow-up fix (2026-05-14, during smoke test):** Haiku was being called
> with default `temperature=1.0` and flipping between hooks across
> otherwise-identical requests, which produced spurious cache misses (different
> hook → different `(topic, difficulty, hook)` key). Live evidence: a third
> identical Invoke-RestMethod call returned a *new* `problem_id` because Haiku
> changed its mind, then a fourth call landed back on the new id. Fix shipped
> by adding an optional `temperature` parameter to `call_json` in
> [../api/anthropic_client.py](../api/anthropic_client.py) and passing
> `temperature=0` from `match_hook`. Sonnet still uses the default (1.0) on
> purpose — we want creative variety on cache miss, and the cache itself
> eliminates determinism concerns on hits. Tests assert temperature=0 on the
> Haiku call and assert no `temperature` kwarg on the Sonnet call.
>
> Known **inefficiency not addressed:** Haiku still runs on every request,
> including cache hits (~$0.0001 per hit). Fixing this requires either
> reordering cache lookup before Haiku (loses multi-hook-variant caching) or
> changing the cache key. Deferred — flagged for revisit if cost dashboard in
> Phase 6 shows it matters.

- **`match_hook` helper** in
  [../api/routes/generate_problem.py](../api/routes/generate_problem.py)
  replaces `pick_hook_stub`. Skips the Haiku call entirely when the topic
  has 0 candidate hooks (the answer is unambiguous; avoids a wasted
  `llm_calls` row). With ≥1 candidate, always calls Haiku — even with a
  single candidate, because the "this is a contrived fit, return null"
  verdict is information worth paying ~$0.0001 for.
- **`HookMatch` pydantic schema** in
  [../api/schemas.py](../api/schemas.py): `hook_slug: str | None` plus
  optional `reason`.
- **Candidate cap** at `MAX_HOOK_CANDIDATES = 6` per the spec. Defensive;
  most topics have 0–3 candidates today.
- **Defensive fallback**: if Haiku returns a slug not in the shortlist (a
  hallucination — system prompt forbids it, but the model can still err),
  treat as `None` and log a warning rather than crashing.
- **Prompt convention divergence**: kept the `build_system_prompt` /
  `build_user_prompt` naming from `prompts/problem.py` instead of the
  stub's `build_hook_match_prompt`. The route imports them as
  `from prompts import hook_match as hook_match_prompts` to avoid clashes
  with `prompts.problem` (which is imported by short name). If a third
  prompt module joins, prefer the module-prefix style throughout.
- **Tests**: new [../api/tests/test_hook_match.py](../api/tests/test_hook_match.py)
  covers the no-candidates skip, picked-slug → hook dict, null-verdict,
  invalid-slug fallback, and the 6-candidate cap. The existing
  `test_hook_match_passes_summary_into_user_prompt` end-to-end test now
  queues a Haiku response *and* a Sonnet response;
  `test_haiku_rejects_hook_falls_back_to_null_cache_key` is new and
  verifies the cache lookup uses `is_null` when Haiku declines. Total: 30
  tests, ruff clean. No live LLM hit yet — see "next session" above.

## Step 6 — Next.js wiring

### Original sketch

- New `web/lib/dailyAssignment.ts` server helper: `ensureTodaysAssignment(userId)`.
  Picks the active plan_node (or first pending), POSTs to Python, persists
  `daily_assignments` (problem_id + plan_node_id + assigned_for_date = today).
  Idempotent on `(user_id, assigned_for_date)` (existing unique constraint).
- New `web/lib/markdown.ts`: marked + KaTeX render of the full markdown+LaTeX
  string. We already have [LatexBlock.tsx](../web/components/LatexBlock.tsx)
  for inline KaTeX; extend for a full document pass.
- Replace [web/app/daily/page.tsx](../web/app/daily/page.tsx) (currently
  hardcoded HTML) with a server component that:
  - Calls `ensureTodaysAssignment(user.id)`
  - Loads the problem + hints + (optional) context hook
  - Renders context first, then statement, then a `<details>` hints panel,
    then the existing submit-solution link to [/upload](../web/app/upload/page.tsx)
- The /upload submit button stays mocked (still shows the "Phase 1"
  placeholder). Vision parsing is Phase 4.

### Step 6 — decisions locked in (2026-05-14)

Worked through with the operator before execution. Don't re-litigate:

- **Markdown renderer: `react-markdown` + `remark-math` + `rehype-katex`** (not
  `marked`). Reasons: JSX output composes with the React tree without
  `dangerouslySetInnerHTML`; raw HTML in markdown is escaped by default
  (safer for Phase 4's user-editable parsed solutions); component overrides
  let us swap inline widgets later (Phase 5 grading feedback). KaTeX
  dominates bundle size (~270 KB) so the extra ~30 KB over `marked` is in
  the noise.
- **No-plan / no-candidate-node state**:
  - No active plan → redirect to [/plan](../web/app/plan/page.tsx).
  - Plan exists but all nodes mastered → static "🎉 plan complete" page with
    a CTA to extend the plan (link back to [/survey](../web/app/survey/page.tsx)
    to add new target topics). The operator wanted an LLM-generated congrats
    message ideally, but the all-mastered case is effectively unreachable in
    Phase 3 (no grading → no mastered transitions), so static text is dead
    code we keep simple. Swapping in a Haiku-generated message later is
    one-line. **Deferred**.
- **Cold-gen loading state**: meaningful `web/app/daily/loading.tsx`
  skeleton (context box + statement box + hints accordion in muted grey)
  for the ~10–30 s cold Sonnet wait.
- **Day-key timezone**: local TZ, not UTC. A friend in Tokyo and the
  operator in San Francisco should each get one problem on their own day.
  Implement with `Intl.DateTimeFormat` using `Intl.DateTimeFormat().resolvedOptions().timeZone`
  on the server to get the user's TZ from their browser preference (we
  don't store TZ yet — store it later if cross-TZ users hit edge cases).
- **One-per-day is NOT a hard gate.** The operator explicitly wants users to
  be able to do multiple problems if they want to. The current
  `daily_assignments` schema has `unique (user_id, assigned_for_date)` which
  *would* gate at one per day. **Step 6 keeps the gate** (since the "extra
  problem" UX isn't designed yet), but **flag in the handoff** that the
  unique constraint is a v1 limitation, not a permanent feature. Likely
  future shape: keep one canonical "today's problem" but allow extra
  on-demand `bonus_assignments` rows. Don't paint into a corner on the
  schema today.
- **Bundle step 8 docs touch-up with step 6.** Tiny, single diff is cleaner.

### Step 6 — file plan

| File | Change |
|---|---|
| `web/package.json` | add `react-markdown`, `remark-math`, `rehype-katex`. `katex` is already a direct dep. |
| `web/lib/pythonApi.ts` *(new)* | `generateProblem({userId, planNodeId})` — POSTs to `${PYTHON_API_URL}/generate-problem` with `Authorization: Bearer ${INTERNAL_API_TOKEN}`, parses `{problem_id}`, throws on non-2xx with the response body in the message. |
| `web/lib/dailyAssignment.ts` *(new)* | `ensureTodaysAssignment(userId)` — service-role Supabase client (same pattern as [web/app/api/plan/approve/route.ts:17-20](../web/app/api/plan/approve/route.ts#L17-L20)). Flow: today-in-local-TZ lookup → existing assignment hit returns bundle; else find active plan + active-or-first-pending plan_node → 404-equivalent (`null`) if no candidate → POST to Python → INSERT `daily_assignments` with try/except on unique violation, re-select on race. Returns `{ assignment, problem, hints, contextHook? }`. **Don't** select `solution_md` for the daily view — the client never needs it; gating defence-in-depth alongside RLS. |
| `web/lib/markdown.tsx` *(new)* | `<MarkdownLatex source={...} />` server component wrapping `react-markdown` with `remark-math` + `rehype-katex`. Load `katex/dist/katex.min.css` from [web/app/layout.tsx](../web/app/layout.tsx). |
| `web/lib/types.ts` | Extend with `Problem`, `ProblemHint`, `ContextHook`, `DailyAssignment` matching the Phase 3 schema. Don't include `solution_md` or `rubric_md` in the client-shipped `Problem` type — those are server-only. |
| `web/app/daily/page.tsx` | **Rewrite** as `async function DailyPage()`. Get user → redirect to /signin if missing → `ensureTodaysAssignment(user.id)` → if no candidate, render the static completion page with link to /survey → otherwise render context (hook summary OR `generated_context_md` via `<MarkdownLatex>`), statement, `<details>` hints, submit link. Keep current Tailwind look. |
| `web/app/daily/loading.tsx` *(new)* | Skeleton. |
| `web/.env.local.example` | Add `PYTHON_API_URL=http://localhost:8000` and `INTERNAL_API_TOKEN=`. |
| [../CLAUDE.md](../CLAUDE.md) | Update `Commands` section: replace Python placeholder with `uv run uvicorn main:app --reload` from `api/`. Note `PYTHON_API_URL` and `INTERNAL_API_TOKEN` env vars. |
| `web/components/LatexBlock.tsx` | Becomes redundant once `<MarkdownLatex>` handles math inside markdown. Can be deleted after the rewrite if nothing else references it. |

### Step 6 — things to watch for

- **Next.js 16, not 15.** Auth proxy lives at [web/proxy.ts](../web/proxy.ts),
  exported function is `proxy`. Don't invent `middleware.ts`. Tailwind v4
  syntax: `@import "tailwindcss"` not `@tailwind`. `web/` has its own
  `.git`. See [web/AGENTS.md](../web/AGENTS.md) — assume Next.js docs at
  `web/node_modules/next/dist/docs/` are the source of truth, not training
  data.
- **`fetch` is no longer cached by default** in Next.js 16. For the
  Python-API call this is what we want; just be aware not to add accidental
  reliance on cache.
- **No Jest setup in `web/`** — smoke-test through the dev server only.
  Call out in handoff doc that automated coverage of the page is missing.
- **No live `/generate-problem` race test.** The race-loss exception path
  in [api/routes/generate_problem.py](../api/routes/generate_problem.py)
  has never been hit live. Step 6 won't change that.

### Step 6 — what shipped

Implementation matches the file plan above, with these deviations / details
worth not re-litigating:

- **Day-key TZ ended up *server*-local, not user-local.** The locked-in
  decision was user-local via the browser's
  `Intl.DateTimeFormat().resolvedOptions().timeZone`, but a Next.js server
  component doesn't see that without a round trip. Shipped as server-local
  (`new Date()` parts) with a `// TODO` comment in
  [../web/lib/dailyAssignment.ts](../web/lib/dailyAssignment.ts) `todayKey()`.
  Same end result for an SF-based operator; only matters when a
  significantly-offset user actually shows up. Carried into the Phase 4
  handoff as follow-up #1.
- **`solution_md` / `rubric_md` deliberately *omitted* from `Problem` type**
  in [../web/lib/types.ts](../web/lib/types.ts) and from the
  `PROBLEM_CLIENT_COLUMNS` select-list in
  [../web/lib/dailyAssignment.ts](../web/lib/dailyAssignment.ts). Defence in
  depth alongside the RLS policy from migration 20250005. Server-side code
  that needs them (Phase 5 grading) will need its own select with the
  service-role client.
- **supabase-js typing quirk**: `.single()`'s `data` is typed as `T |
  GenericStringError` (both truthy), so the `if (err || !data) throw` check
  doesn't narrow. Cast with `as unknown as Problem` after the check rather
  than reshape every helper to please the type system.
- **`react-markdown` v10** (released after the original plan was written)
  has `MarkdownAsync` and `MarkdownHooks` variants alongside the default
  `Markdown`. Using plain `Markdown` — synchronous server-render is exactly
  what we want.
- **`@tailwindcss/typography` is not installed**, so the `prose` classes I
  sprinkled on `<MarkdownLatex>` calls are dead weight today. Markdown
  still renders, just without article-style margins. Carried as follow-up
  #2 (Phase 4's review UI will want this anyway, so install at that point).
- **`LatexBlock.tsx` deleted.** Was the only place `katex.renderToString`
  was called directly; `<MarkdownLatex>` subsumes it. The
  `katex/dist/katex.min.css` import in
  [../web/app/layout.tsx](../web/app/layout.tsx) stays — `rehype-katex`
  needs the stylesheet to be loaded at the page level.
- **Build is clean, lint is clean.** No automated tests for the new
  `web/lib/` files — `web/` has no Jest setup and Phase 6 is the right time
  to consider one. Live smoke-tested instead.
- **First-run gotcha shipped:** the new env vars
  (`PYTHON_API_URL`, `INTERNAL_API_TOKEN`) need to be added to
  `web/.env.local` — `.env.local.example` was updated but operator's
  `.env.local` was not. Runtime error is clear (`PYTHON_API_URL is not
  set`); just a one-time setup step on each fresh checkout.

## Step 7 — Difficulty mapping

Without struggle signals (Phase 5), pick the problem difficulty from the
user's `surveys.difficulty_curve` and the topic's `difficulty_band`:

| difficulty_curve | intro topic | core topic | advanced topic |
|---|---|---|---|
| gentle | 1 | 2 | 3 |
| standard | 2 | 3 | 4 |
| aggressive | 3 | 4 | 5 |

Encode as a small helper, probably in the Python service since the mapping is
used at generation time.

## Step 8 — Docs touch-ups

- Root [CLAUDE.md](../CLAUDE.md) `Commands` section: replace the Python
  placeholder with the actual `uv` / `uvicorn` commands and add the two new
  env vars (`PYTHON_API_URL`, `INTERNAL_API_TOKEN`).
- [web/.env.local.example](../web/.env.local.example): add
  `PYTHON_API_URL=http://localhost:8000` and `INTERNAL_API_TOKEN=`.

## Risks to watch in steps 3–8

- **Claude returning malformed JSON for the 5-hint structure.** Mitigation:
  JSON-mode response + pydantic parse + one retry with tightened prompt. Log
  both attempts so we can audit later.
- **Cold first-visit latency** (~10–20s for Sonnet generation when cache
  misses). Acceptable for a private app with ~10 users; document on the
  daily page. If it becomes a problem, add a cron pre-warm in Phase 6.
- **Mixing `marked` + KaTeX is fiddly.** Build a focused render test page
  first (e.g., `/test/render`) before wiring into `/daily`.
- **Hook bias.** If the seeded hooks skew toward physics (they do), math
  topics will more often fall through to "generated context". That's fine
  for Phase 3; expand seed in Phase 6 if it's an issue.

## Things easy to forget (from CLAUDE.md / SPEC.md / ARCHITECTURE.md)

- **Next.js 16, not 15.** Route protection lives in
  [web/proxy.ts](../web/proxy.ts), exported function is `proxy`. Don't
  invent `middleware.ts`.
- **Tailwind v4.** `@import "tailwindcss"`, not `@tailwind`.
- **`web/` has its own `.git`** initialised by create-next-app.
- **Hints are pre-generated at problem creation time and stored.** Never on
  demand. Prevents drift and accidental answer leakage. (SPEC.md §Hints.)
- **Vision parse is always user-reviewed** before grading (Phase 4 concern,
  not Phase 3, but easy to design around incorrectly).
- **Disputed grades are queued for operator review.** No auto-regrading in
  v1.
- **Cache key**: `(canonical_topic_id, difficulty, context_hook_id)`. Shared
  across users unless operator explicitly disables.
- **Sonnet 4.6** = `claude-sonnet-4-6`. **Haiku** = `claude-haiku-4-5-20251001`.
- **Every Claude call must be logged to `llm_calls`** — route, model, token
  counts (incl. cache), USD cost.
