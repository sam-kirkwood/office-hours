Status: Phase 4-rev in progress — migrations done (steps 1–6), code steps pending. Last commit: 731c644.
Next step: Phase 4-rev step 7 — FastAPI POST /add-interest.

---

# Reconciliation plan: v1 → v2 pivot

## Context

The product was redesigned mid-build. v1 was a plan-walking curriculum tutor with a static topic graph (`canonical_topics`/`canonical_edges`) and one-problem-per-day assignments driven by a generated `user_plans`/`plan_nodes` tree. v2 ([SPEC.md](../SPEC.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [docs/graph-design.md](graph-design.md), [docs/personas.md](personas.md)) replaces the plan with an evolving **queue**, splits the topic graph into a **two-layer megagraph** (operator-curated foundation nodes + user-grown interest nodes, deduplicated and shared across the user base), and adds **paper engagement** as a first-class content mode alongside problems.

The repo currently contains:
- 7 applied migrations (`20250001`–`20250007`), seeding 21 canonical topics, 28 edges, ~30 context hooks, and a vision-parsing-ready `attempts` table.
- A Next.js app with survey → plan-review → daily-assignment flow wired end-to-end.
- A FastAPI service exposing only `/generate-problem` (with Haiku hook-matching + Sonnet generation + `llm_calls` logging).

No real user data exists yet — the pivot is structural, not data-preserving. The reconciliation is therefore a code-and-schema migration, not a data migration.

This plan answers six prompts (A–F) and lays out the phased execution order from `ARCHITECTURE.md → Build phases (revised)`, broken into per-step commits.

---

## A. Survives unchanged

These carry forward as-is; no schema or behaviour change required.

### Tables
- `profiles` — auth/identity unchanged.
- `problem_hints` — `(problem_id, level, text)` shape still matches v2's pre-generated-at-creation-time constraint.
- `context_hooks` — still used; v2 keeps the curated historical hooks. Note `related_topic_ids uuid[]` references rows that will be migrated into `nodes` (same UUIDs preserved — see section B), so the FK semantics survive even though the target table changes.
- `llm_calls` — schema is already what `ARCHITECTURE.md` calls for. Continue logging every Claude call here.

### Code
- [api/anthropic_client.py](../api/anthropic_client.py) — `call_json`, `log_llm_call`, pricing dict, retry-once-on-parse-failure pattern. Reused unchanged by all v2 routes.
- [api/config.py](../api/config.py), [api/auth.py](../api/auth.py), [api/supabase_client.py](../api/supabase_client.py) — internal-token auth and Supabase client factory.
- [api/difficulty.py](../api/difficulty.py) — `difficulty_for(curve, band)` still applies; v2 keeps difficulty bands per node.
- [api/prompts/hook_match.py](../api/prompts/hook_match.py) — hook-matching prompt unchanged.
- [web/proxy.ts](../web/proxy.ts) — Next.js 16 auth middleware. The pages it gates change, but the proxy itself doesn't.
- [web/lib/supabase/client.ts](../web/lib/supabase/client.ts), [web/lib/supabase/server.ts](../web/lib/supabase/server.ts) — Supabase client factories.
- [web/lib/markdown.tsx](../web/lib/markdown.tsx) — markdown+LaTeX rendering; v2 needs this in more places, not fewer.
- [web/app/signin/page.tsx](../web/app/signin/page.tsx), [web/app/api/auth/callback/route.ts](../web/app/api/auth/callback/route.ts) — auth flow.

### Seed data
- All 21 canonical topics (rows, slugs, descriptions, subtopics) and all 28 prerequisite edges — preserved as the seed for `nodes` and `edges` (see B and D).
- All ~30 context hooks (slugs, summaries, related-topic UUIDs) — survive untouched.

---

## B. Modified (column-level deltas)

### Tables

**`surveys`** — restructured for v2 onboarding (free-text intent + node ratings + comfort responses + mode-balance slider).

| Action | Column | Notes |
|---|---|---|
| DROP | `background_json` | Replaced by `free_text_intent` (single sentence). |
| DROP | `topic_states_json` | Replaced by `node_ratings_json` keyed by node slug. |
| DROP | `difficulty_curve` | v2 has per-problem easier/harder dial; no global curve. |
| KEEP | `id`, `user_id`, `created_at` | Unchanged. |
| ADD | `free_text_intent text` | Required. |
| ADD | `node_ratings_json jsonb` | `{node_slug: "interested" | "comfortable" | "refresh"}`. |
| ADD | `comfort_responses_json jsonb` | Open-ended question responses. |
| ADD | `mode_balance real` | 0.0 = all problems, 1.0 = all papers (interpretation needs confirmation — see F2). |
| ADD | `updated_at timestamptz default now()` | Required for the "revisit survey" flow personas mention. |

**`problems`** — pivot off the new graph, add immutability-by-versioning, paper-tied marker, pool status, time estimates, and the inline-context column.

| Action | Column | Notes |
|---|---|---|
| RENAME | `canonical_topic_id` → `topic_node_id` | FK target changes from `canonical_topics(id)` to `nodes(id)`. Same UUIDs after seed migration. |
| KEEP | `statement_md`, `solution_md`, `rubric_md`, `difficulty`, `context_hook_id`, `generated_context_md`, `generated_by_llm_call_id`, `created_at` | All survive. |
| ADD | `version smallint not null default 1` | Immutability via versioning. |
| ADD | `previous_version_id uuid references problems(id)` | Edit-history chain. |
| ADD | `tags text[] not null default '{}'` | For queue-side filtering and "requested subtopic" surfacing. |
| ADD | `paper_id uuid references papers(id)` | Non-null = paper-tied; excluded from generic pool reuse (CLAUDE.md). |
| ADD | `pool_status text default 'active'` | check in `('active','retired','flagged')`. |
| ADD | `time_estimate_minutes_low smallint`, `time_estimate_minutes_high smallint` | For the "why this" line on queue items. |
| RENAME | `generated_context_md` → `context_md` | Same column, cleaner name. No new column added. |
| MODIFY | The two partial unique indexes `problems_cache_key_with_hook` and `problems_cache_key_no_hook` must be rewritten to use `topic_node_id` and to exclude rows with `paper_id IS NOT NULL` (paper-tied problems aren't pool-reusable). |

**`attempts`** — add the three v2 user-control flags + sibling-chain link.

| Action | Column | Notes |
|---|---|---|
| KEEP | All existing columns from `20250001` and `20250007`: `id`, `user_id`, `problem_id`, `raw_image_paths`, `parsed_markdown`, `user_edited_markdown`, `hint_levels_used`, `parse_status`, `parsed_by_llm_call_id`, `submitted_at`, `created_at`. |
| DROP | `assignment_id` | No live data; dropped in step 4-rev.4 alongside the `daily_assignments` deprecation. Replaced by `queue_item_id`. |
| DROP | `attempts_one_per_assignment` unique constraint | Coupled to deprecated `daily_assignments`. |
| ADD | `queue_item_id uuid references queue_items(id)` | Replaces `assignment_id` as the link from an attempt to its queue context. |
| ADD | `marked_refreshed boolean not null default false` | Set by user via "mark as refreshed". |
| ADD | `requested_easier boolean not null default false` | Set at submit time. |
| ADD | `requested_harder boolean not null default false` | Set at submit time. |
| ADD | `parent_attempt_id uuid references attempts(id)` | For sibling-attempt chains after easier/harder requests. |
| ADD | `grade_response_md text` | Claude's dialogic response to the submission. Stored on `attempts` (not only in `notebook_entries`) so the problem-completion screen can show it without a cross-table join. |
| ADD | `disputed boolean not null default false` | Set by user if they disagree with the feedback; flagged for operator review in curation. |

### Code

**FastAPI service**
- [api/main.py](../api/main.py) — register all new route modules listed in section D.
- [api/routes/generate_problem.py](../api/routes/generate_problem.py) — change every reference to `canonical_topics`, `plan_nodes`, `surveys.difficulty_curve`. Inputs now arrive from the queue, not the plan. Lookups switch to `nodes`. Difficulty is derived from `user_node_states.struggle_score` + per-problem easier/harder request, not from a global curve.
- [api/prompts/problem.py](../api/prompts/problem.py) — minor: prompt still produces `(statement, solution, rubric, hints, context)` but is now parametrised on node title/description/subtopics from the `nodes` table.
- [api/schemas.py](../api/schemas.py) — add request/response models for every new endpoint (see D).

**Next.js app**
- [web/app/api/survey/route.ts](../web/app/api/survey/route.ts) — rewrite to write the new survey shape, call `/add-interest` for any free-text-derived interests, and seed `queue_items` instead of `user_plans`/`plan_nodes`.
- [web/app/survey/page.tsx](../web/app/survey/page.tsx) and [web/components/SurveyForm.tsx](../web/components/SurveyForm.tsx) — UI rewrite: free-text intent, node-rating step, comfort questions, mode-balance slider.
- [web/lib/dailyAssignment.ts](../web/lib/dailyAssignment.ts) — replaced by a new `surfaceDaily` helper that hits the queue, not `daily_assignments`. Existing race-safe-insert pattern is reusable.
- [web/lib/types.ts](../web/lib/types.ts) — replace `CanonicalTopic`, `CanonicalEdge`, `UserPlan`, `PlanNode`, `TopicState`, `TopicStateMap`, `SurveyPayload`, `DailyAssignment` with the v2 equivalents (`Node`, `Edge`, `QueueItem`, `SurfacedPick`, `UserNodeState`, `UserInterest`, etc.).
- [web/lib/pythonApi.ts](../web/lib/pythonApi.ts) — add typed wrappers for every new FastAPI route.
- [web/app/daily/page.tsx](../web/app/daily/page.tsx) — repurposed to show the three surfaced items rather than a single daily assignment.

---

## C. Deprecated

Kept briefly (no new writes) so the v1 seed history isn't lost; dropped in Phase 8-rev or later once the operator UI no longer references them.

### Tables (no new writes from Phase 4-rev onward; physical DROP later)
- `canonical_topics` — replaced by `nodes` (kind='foundation' for the 13, kind='interest' for the 8).
- `canonical_edges` — replaced by `edges` (edge_kind='prerequisite').
- `user_plans` — replaced by `queue_items` + `surfaced_picks`.
- `plan_nodes` — replaced by `queue_items`.
- `daily_assignments` — replaced by `surfaced_picks` (and `queue_items` for the underlying content).
- `pending_topic_requests` — **not listed in CLAUDE.md's deprecation list**, but it's the v1 mechanism for "user typed an extra topic during survey" and is fully superseded by `/add-interest` + autonomous dedup. See F5.

### Code to delete or rewrite end-to-end
- [web/app/api/plan/approve/route.ts](../web/app/api/plan/approve/route.ts) — entire route; no plan-approval flow in v2.
- [web/app/api/plan/adjust/route.ts](../web/app/api/plan/adjust/route.ts) — entire route.
- [web/app/plan/page.tsx](../web/app/plan/page.tsx) — entire page (the plan-review UI). Skill tree view in Phase 5-rev is functionally different (it's discovery, not review-and-approve).
- [web/lib/plan.ts](../web/lib/plan.ts) — `generatePlan(...)` graph-traversal helper. The queue is built by `/update-queue` (FastAPI), not by client-side BFS.
- [web/components/PlanGraph.tsx](../web/components/PlanGraph.tsx), [web/components/SkillTree.tsx](../web/components/SkillTree.tsx), [web/components/SkillTreeView.tsx](../web/components/SkillTreeView.tsx) — the v1 plan-graph components. v2's skill tree view (Phase 5-rev) uses React Flow + Dagre against `nodes`/`edges` with state from `user_node_states`. The old components don't carry forward.

---

## D. New (tables and code)

### Tables (Phase 4-rev migration)

```
nodes               foundation | interest, slug, title, description_md, domain,
                    difficulty_hint, subtopics_json, unlocks_text, pool_status,
                    created_by_user_id (null for foundations), created_at, updated_at

edges               source_node_id → target_node_id, edge_kind (prerequisite|related),
                    weight, created_at

user_node_states    user_id, node_id, state (unseen|bookmarked|active|struggling|comfortable),
                    engagement_count, struggle_score, last_engaged_at

user_interests      user_id, node_id, weight, added_via (survey|explicit_request|cross_pollination),
                    created_at

queue_items         user_id, kind (problem|paper_engagement|refresher|concept_review|suggested_interest),
                    ref_id (polymorphic), state (pending|surfaced|in_progress|done|skipped|dismissed),
                    priority_score, time_estimate_minutes_low/high, added_reason,
                    added_at, updated_at

surfaced_picks      user_id, queue_item_ids uuid[] (length 3 — see F8), surfaced_at,
                    replaced_at, chosen_item_id

papers              title, authors_json, year, arxiv_id (nullable unique),
                    doi (nullable unique), external_url, abstract_md, created_at

paper_engagements   user_id, paper_id, why_this_md, orienting_concepts_json,
                    questions_json, state, current_question_index, created_at,
                    updated_at, completed_at

paper_answers       engagement_id, question_id, user_response_md, claude_response_md,
                    submitted_at

paper_qa            engagement_id, turn_index, user_message_md, claude_response_md, created_at

notebook_entries    user_id, entry_kind (problem_attempt|paper_engagement), ref_id,
                    title, topic_node_slugs text[], created_at, updated_at  +  FTS index

bookmarks           user_id, kind (node|paper|problem|concept), ref_id_or_text,
                    created_at, promoted_at

refresher_schedule  user_id, subject_kind (attempt|engagement|concept),
                    subject_ref_id, due_at, surfaced_at

curation_proposals  kind (merge|split|rename|promote|demote|add_edge|deprecate),
                    payload_json, status (pending|approved|rejected|applied),
                    proposed_at, decided_at, decided_by

megagraph_snapshots label, snapshot_json, taken_at, taken_by (system|operator)
```

RLS: every per-user table (`user_node_states`, `user_interests`, `queue_items`, `surfaced_picks`, `paper_engagements`, `paper_answers`, `paper_qa`, `notebook_entries`, `bookmarks`, `refresher_schedule`) gates on `auth.uid() = user_id` like existing tables. `nodes`/`edges`/`papers`/`curation_proposals`/`megagraph_snapshots` are admin-or-read-all (RLS TBD per route).

### FastAPI routes (new modules under `api/routes/`)

| Route | Model | Purpose |
|---|---|---|
| `POST /generate-problem` | Sonnet | Existing — adapted to read from `nodes` instead of `canonical_topics`. |
| `POST /parse-solution` | Sonnet (vision) | **Not yet implemented** — Phase 4 step 1 in v1 plan only got as far as the migration. Phase 4-rev or 5-rev finishes this. See F6. |
| `POST /grade-solution` | Sonnet | Dialogic feedback (not graded). Writes to `attempts.grade_response_md` (column name TBD) and creates a `notebook_entries` row. |
| `POST /generate-paper-engagement` | Sonnet | Pre-generates why-this, orienting concepts, questions when paper enters queue. |
| `POST /grade-paper-answer` | Sonnet | Per-question dialogic response. |
| `POST /paper-question` | Sonnet | Free-form Q&A turn. |
| `POST /suggest-papers` | Sonnet | Background job; produces paper candidates from interests. v2.1 will use live arXiv. |
| `POST /surface-daily` | none (deterministic) | Picks 3 varied items from `queue_items` → writes `surfaced_picks`. |
| `POST /update-queue` | Haiku/Sonnet | Recompute priority, prune, add refreshers after each attempt/engagement. |
| `POST /add-interest` | Haiku (dedup) + Sonnet (generate) | The interest-add flow from graph-design.md. |
| `POST /generate-curation-report` | Sonnet | Weekly. Reads recent megagraph changes, produces `curation_proposals` rows. |
| `POST /compute-cross-pollination` | none (deterministic ranking) | Daily background; gated on first curation having completed. |

### Next.js API routes (new under `web/app/api/`)

`/api/queue` (GET surfaced items), `/api/queue/reroll`, `/api/queue/request`, `/api/queue/bookmark`, `/api/interest` (POST add new), `/api/graph/me`, `/api/graph/admin`, `/api/problem/[id]`, `/api/problem/[id]/submit`, `/api/paper/[id]`, `/api/paper/[id]/submit-answer`, `/api/paper/[id]/ask`, `/api/notebook`, `/api/admin/*`. `/api/upload/sign` stub is upgraded to real signed-URL issuance.

### Next.js pages
- `/daily` rewritten to show three surfaced items (was: single assignment).
- `/skill-tree` — new (Phase 5-rev). React Flow + Dagre.
- `/notebook` — new (Phase 5-rev/6-rev). List + read views with FTS.
- `/paper/[id]` — new (Phase 6-rev). Engagement UI with multi-session resume.
- `/admin/*` — new (Phase 8-rev). Curation review, megagraph view, snapshot management, cost dashboard.
- `/survey` UI rewritten for new survey shape.

---

## E. Recommended phase order (per ARCHITECTURE.md, broken into commit-sized steps)

Each step is one commit. The pivot-plan status line (top of this file) tracks the current step. Steps within a phase must land in order. Do not start phase N until the prior phase is committed and the status line is updated.

### Phase 4-rev — Graph migration & queue foundation

1. **`20250008_graph_schema.sql`** — create `nodes`, `edges`, `user_node_states`, `user_interests`, `bookmarks`, `curation_proposals`, `megagraph_snapshots`. Indexes + RLS.
2. **`20250009_queue_schema.sql`** — create `queue_items`, `surfaced_picks`, `refresher_schedule`. Indexes + RLS.
3. **`20250010_papers_schema.sql`** — create `papers`, `paper_engagements`, `paper_answers`, `paper_qa`, `notebook_entries` (with FTS index). Indexes + RLS.
4. **`20250011_modify_problems_attempts_surveys.sql`** — apply the column-level changes from section B to `problems`, `attempts`, `surveys`. Specifically: drop `attempts.assignment_id` and `attempts_one_per_assignment` constraint (no live data); add `queue_item_id`, `marked_refreshed`, `requested_easier`, `requested_harder`, `parent_attempt_id`, `grade_response_md`, `disputed` to `attempts`; rename `problems.generated_context_md` → `context_md`; add remaining `problems` columns; restructure `surveys`. Rewrite the two `problems_cache_key_*` partial unique indexes using `topic_node_id`.
5. **`20250012_seed_nodes_edges.sql`** — copy 13 canonical_topics → nodes (kind='foundation') and 8 → nodes (kind='interest'), preserving UUIDs so `context_hooks.related_topic_ids` still resolves; copy 28 canonical_edges → edges (edge_kind='prerequisite'); update `problems.topic_node_id` from the old `canonical_topic_id`.
6. **`20250013_deprecate_v1_tables.sql`** — leave `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`, `pending_topic_requests` in place; revoke INSERT/UPDATE privileges (or add `comment on table … is 'DEPRECATED'` + a deferred-drop ticket). Don't drop yet — operator might want to introspect history.
7. **FastAPI `POST /add-interest`** — Haiku-dedup + Sonnet-generate (see graph-design.md). New module `api/routes/add_interest.py` + prompts.
8. **FastAPI `POST /surface-daily` + `POST /update-queue` (initial)** — deterministic surfacing logic; queue update is initially a no-op skeleton.
9. **Next.js: new survey UI** — rewrite `web/app/survey/page.tsx`, `web/components/SurveyForm.tsx`, `web/app/api/survey/route.ts`. Free-text intent → `/add-interest` calls; node ratings → seed `user_node_states`; mode-balance slider; comfort responses.
10. **Next.js: queue read endpoint** — `web/app/api/queue/route.ts` (GET surfaced items). `web/app/api/interest/route.ts` (POST add new).
11. **Next.js: daily-three page (mocked content acceptable)** — rewrite `web/app/daily/page.tsx`. Validates layout end-to-end with stub data.
12. **Delete deprecated code** — remove `web/app/api/plan/*`, `web/app/plan/page.tsx`, `web/lib/plan.ts`, `web/components/Plan*.tsx`, `web/components/SkillTree*.tsx`. Update [CLAUDE.md](../CLAUDE.md) once removed.
13. **Phase 4-rev acceptance** — new user signs up, completes new survey, megagraph populated with their interests, lands on `/daily` and sees three (mocked) items. Update status line.

### Phase 5-rev — Skill tree & graph-driven problem flow

1. **FastAPI `POST /parse-solution`** — vision route. Schema already in place from `20250007`. This is the unfinished v1 Phase 4 step.
2. **FastAPI `POST /grade-solution`** — dialogic feedback. Writes back to `attempts` and creates a `notebook_entries` row.
3. **FastAPI: refactor `/generate-problem`** — read from `nodes` not `canonical_topics`; tie to queue_item, not plan_node.
4. **Next.js: real problem flow** — `web/app/problem/[id]/page.tsx`, `web/app/api/problem/[id]/route.ts`, `web/app/api/problem/[id]/submit/route.ts`. Connects upload → parse → review → submit → grade → notebook.
5. **Next.js: "mark as refreshed"** — sets `attempts.marked_refreshed=true` and updates `user_node_states`.
6. **Next.js: notebook browse + read** — `web/app/notebook/page.tsx`, `web/app/notebook/[id]/page.tsx`, `/api/notebook` endpoint.
7. **Next.js: skill tree view** — `web/app/skill-tree/page.tsx`. React Flow + Dagre. `/api/graph/me` returns the user's slice + adjacent regions.
8. **Phase 5-rev acceptance** — real problem flow works end-to-end; user can browse skill tree. Update status line.

### Phase 6-rev — Paper engagement

1. **FastAPI: papers ingestion** — minimal `/admin/papers` ingestion endpoint (manual title/authors/arxiv_id entry; v2.1 will replace with live arXiv).
2. **FastAPI `POST /generate-paper-engagement`** — pre-generates why-this, orienting concepts, questions when a paper enters a user's queue.
3. **FastAPI `POST /grade-paper-answer`** — dialogic per-question response.
4. **FastAPI `POST /paper-question`** — free-form Q&A turn.
5. **FastAPI `POST /suggest-papers`** — background job; reads `user_interests`, produces paper candidates.
6. **Next.js: paper engagement UI** — `web/app/paper/[id]/page.tsx`, `/api/paper/[id]/*` routes. Multi-session resume on `current_question_index`.
7. **Next.js: notebook entries for papers** — extend the Phase 5-rev notebook to render paper engagements (questions, answers, Q&A turns).
8. **Phase 6-rev acceptance** — paper loop works including system-suggested papers. Update status line.

### Phase 7-rev — Adaptation, refreshers, cross-pollination

1. **FastAPI: real `/update-queue`** — after each attempt/engagement, recompute `priority_score`, retire done items, add refreshers to `refresher_schedule`.
2. **FastAPI: `user_node_states` recomputation** — engagement_count, struggle_score, state transitions (unseen → active → struggling/comfortable).
3. **FastAPI: refresher surfacing** — refresher items inserted into queue based on `refresher_schedule.due_at`.
4. **Next.js: explicit request flow** — `/api/queue/request` (user typing "give me more X").
5. **FastAPI `POST /compute-cross-pollination`** — daily background; produces `suggested_interest` queue items. Gated on first curation having completed.
6. **Phase 7-rev acceptance** — queue feels responsive; cross-pollination quietly surfaces. Update status line.

### Phase 8-rev — Weekly curation & operator surfaces

1. **FastAPI `POST /generate-curation-report`** — weekly; reads `nodes`/`edges` deltas, autonomous dedup decisions, engagement signals; writes `curation_proposals` rows.
2. **Next.js: admin proposal review UI** — `web/app/admin/curation/page.tsx`. Approve/reject/apply.
3. **Next.js: operator megagraph view** — `web/app/admin/megagraph/page.tsx`. Full graph render, layer toggles, time scrubber over `megagraph_snapshots`.
4. **Snapshot job** — write `megagraph_snapshots` row after every curation round.
5. **Cost dashboard** — `web/app/admin/costs/page.tsx`. Reads `llm_calls`.
6. **Drop deprecated tables** — finally remove `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`, `pending_topic_requests`.
7. **Phase 8-rev acceptance** — operator runs curation; megagraph is maintainable. Update status line.

### Phase 9-rev — Polish

1. Design-system pass on every surface.
2. Mobile polish (queue/notebook are mobile-relevant; skill tree probably desktop-only).
3. Error monitoring (Sentry or similar).
4. Phase 9-rev acceptance — v2 ready for friends.

### Deferred (v2.1+)

Live arXiv search, bespoke D3 megagraph visualisation, notebook calendar view, return-after-absence prompts, BYO API key, notebook export, hand-authored problems, per-user difficulty calibration.

---

## F. Design decisions log

Items resolved before implementation started. Deferred items are flagged with the step where they must be decided.

### Resolved

**F1 — `attempts.assignment_id`:** Drop it outright in step 4-rev.4 (no live data to preserve). Replace with `queue_item_id uuid references queue_items(id)`. The `attempts_one_per_assignment` unique constraint drops with it. Section B updated accordingly.

**F2 — `surveys.mode_balance` direction:** `0.0` = all problems, `1.0` = all papers. Matches the lexical ordering of `queue_items.kind`.

**F3 — Dialogic-grading storage:** `grade_response_md text` and `disputed boolean` live on `attempts` (not only in `notebook_entries`). Rationale: the problem-completion screen fetches the attempt row anyway; adding a cross-table join through `notebook_entries` just to show feedback is unnecessary. `notebook_entries.ref_id` still points at the attempt, so the notebook can surface the response without any schema change. Section B updated accordingly.

**F4 — `context_md` vs `generated_context_md`:** Rename `generated_context_md` → `context_md` in step 4-rev.4. No second column added. Section B updated accordingly.

**F5 — `pending_topic_requests` deprecation:** Confirmed deprecated. Added to the step 4-rev.6 DROP list alongside the other v1 plan tables.

**F6 — Vision parsing phase placement:** `/parse-solution` ships in Phase 5-rev step 1, not Phase 4-rev. Phase 4-rev's daily-three page uses mocked content per ARCHITECTURE.md's deliverable wording.

**F7 — Paper dedup key when no `arxiv_id`/`doi`:** Add a unique constraint on `external_url` for the non-null case; fall back to `(lower(title), year)` as a soft duplicate check for the no-identifier case. Implement in step 6-rev.1.

**F8 — `surfaced_picks` with fewer than 3 eligible items:** Relax to `length ≤ 3`. Surface 1 or 2 with a "more coming" placeholder rather than blocking surfacing entirely. Implement in step 4-rev.8.

**F11 — `paper_engagements.questions_json` schema:** `[{id: uuid, kind: 'comprehension'|'critical'|'connective', prompt_md: string, order: int}]`. Claude generates this array in `/generate-paper-engagement`; `paper_answers.question_id` references the `id` field. Implement in step 6-rev.2.

**F12 — Hint click logging:** Server-side. `attempts.hint_levels_used` (already a `smallint[]`) is written each time a hint is opened via the problem API, not only at submit. Implement in step 5-rev.4.

**F13 — Timezone handling:** `refresher_schedule.due_at` stored as `timestamptz`; resolved against the user's IANA timezone. Add `profiles.timezone text` column in step 4-rev.1 (alongside the `nodes` schema migration is fine). Implement surfacing resolution in step 7-rev.3.

**F14 — Race-safety on `/add-interest` dedup:** Unique constraint on `nodes.slug` (enforced in step 4-rev.1). On slug-collision at insert time, fold the collision into a `curation_proposals` merge row rather than erroring. Implement in step 4-rev.7.

**F15 — `subtopics` → `subtopics_json` rename:** Confirmed. The `nodes` table uses `subtopics_json` to match the `_json` suffix convention on jsonb columns throughout ARCHITECTURE.md. Implement in step 4-rev.1.

### Deferred (must be decided before the blocking step)

**F9 — `queue_items.ref_id` type-by-kind mapping.** For `kind='suggested_interest'`, `ref_id` presumably points at `nodes(id)`. For `kind='concept_review'`, the target is unclear — `nodes(id)` again, or `bookmarks(id)`? Pin down the full kind→table mapping before writing step 4-rev.8 (`/surface-daily`) or step 7-rev.1 (`/update-queue`).

**F10 — What user action writes `user_interests` with `added_via='cross_pollination'`.** Cross-pollination produces a `suggested_interest` queue item. The follow-on write to `user_interests` must be triggered by a specific user action (accept / first engage / bookmark → promote). Decide the trigger and whether `dismissed` items should also write a row (with a different state) before implementing step 7-rev.5.
