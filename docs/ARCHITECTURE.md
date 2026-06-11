# ARCHITECTURE.md — Personalized Science Tutor (v2)

## About this document

This is the second version. The first (in `docs/archive/ARCHITECTURE-v1.md`)
described a plan-based architecture organised around static skill-tree
paths through a canonical curriculum. This version reframes around an
evolving queue, paper engagement as a first-class mode, an accumulating
notebook, and a shared knowledge graph (the megagraph). See
`docs/graph-design.md` for the full graph model; this document covers
infrastructure, data model, services, and build phases.

Significant infrastructure carries forward from v1 unchanged: stack,
auth, storage, FastAPI service scaffold, problem and hints schema, cost
logging. The `canonical_topics`/`canonical_edges` schema is replaced by
a unified `nodes`/`edges` schema; data is migrated. Plan tables are
deprecated.

## Stack

Unchanged from v1.

| Layer            | Choice                                 |
|------------------|----------------------------------------|
| Frontend         | Next.js (App Router, TypeScript)       |
| API (web)        | Next.js API routes                     |
| API (AI service) | Python + FastAPI                       |
| Database         | Postgres (Supabase)                    |
| Auth             | Supabase Auth (email magic links)      |
| File storage     | Supabase Storage                       |
| Hosting (web)    | Vercel                                 |
| Hosting (AI)     | Railway or Fly.io                      |
| LLM              | Anthropic Claude API                   |

Sonnet for problem and paper-engagement generation, grading, dialogic
feedback, interest-node generation, and weekly curation reports. Haiku
for deduplication checks, classification, and other cheap routing.

## Service topology

```
[ Browser ]
     │
     ▼
[ Next.js on Vercel ]
   ├── pages: survey, daily, problem, paper, upload, notebook,
   │           skill tree, admin
   ├── API routes:
   │      /api/auth/*
   │      /api/survey
   │      /api/queue (read surfaced items)
   │      /api/queue/reroll
   │      /api/queue/request
   │      /api/queue/bookmark
   │      /api/queue/resume (deferred → pending; manual "queue it now")
   │      /api/interest (add new)
   │      /api/interest/list (the user's interests; notebook tab strip)
   │      /api/graph/me (the user's slice + adjacent; carries bookmark overlay)
   │      /api/graph/admin (full megagraph; admin only)
   │      /api/node/[id]/bookmark (toggle node bookmark)
   │      /api/problem/[id]
   │      /api/problem/[id]/submit
   │      /api/problem/[id]/defer (→ deferred "come back to this")
   │      /api/paper/[id]
   │      /api/paper/[id]/submit-answer
   │      /api/paper/[id]/ask
   │      /api/upload/sign
   │      /api/notebook
   │      /api/notebook/come-back (bookmarked nodes + deferred items)
   │      /api/admin/*
   └── Calls Python service for AI operations
            │
            ▼
[ Python FastAPI service on Railway/Fly ]
   ├── POST /generate-problem
   ├── POST /parse-solution             (vision)
   ├── POST /grade-solution
   ├── POST /generate-paper-engagement
   ├── POST /grade-paper-answer
   ├── POST /paper-question
   ├── POST /suggest-papers
   ├── POST /propose-papers             (Sonnet; expands paper pool on demand, used as fallback by /api/queue/request)
   ├── POST /ingest-paper-user          (user-supplied arXiv/DOI/title → paper + engagement + queue_item)
   ├── POST /surface-daily              (no LLM; deterministic)
   ├── POST /assess-engagement          (Haiku; post-engagement, Phase 10-rev §3a)
   ├── POST /plan-queue                 (Sonnet; daily per active user, Phase 10-rev §3b)
   ├── POST /check-deferred             (no LLM; conditional re-queue, Phase 10-rev §3c)
   ├── POST /run-daily-planner          (per-user wrapper around /plan-queue + /check-deferred; pg_cron fan-out target, Phase 10-rev §3d)
   ├── POST /concept-review-resolve     (no LLM; pool-hit-or-reading for kind='concept_review' cards, Phase 10-rev §4a; reading miss inlines /generate-concept-brief, §5.5)
   ├── POST /create-refresher           (creation-time resolver — pool lookup at intent='refresh' on the node, generate on miss, concept_review on generation failure; also handles legacy refresher_schedule shape. Writes a directly-routable queue item with via_refresher=true. Replaces the click-time /refresher-resolve, Phase 10.5-rev §2)
   ├── POST /generate-concept-brief     (Haiku; ~250-word concept brief + per-subtopic glosses, cached on node_concept_briefs by node_id, Phase 10-rev §5.5)
   ├── POST /generate-edge-description  (Haiku; 3-5 sentence bridge description, cached on edge_descriptions by edge_id, Phase 10-rev §6 revision)
   ├── POST /add-interest/parse         (dedup + mirror-back; read-only)
   ├── POST /add-interest/resolve       (commits user_interests; opt. Sonnet generate)
   ├── POST /add-interest/rewrite-summaries (Haiku batch; rewrites tag-soup intent_context into prose for the profile page)
   ├── POST /survey/suggest-interests   (Haiku; Stage 3 interest-tile reranker)
   ├── POST /generate-curation-report   (weekly)
   ├── POST /compute-cross-pollination  (daily background)
   └── All Claude API calls; logs to llm_calls
```

## Data model

Tables marked **NEW** are added in v2; **CHANGED** indicates schema
changes; **DEPRECATED** tables remain present briefly during migration.

### Users and onboarding

- `users` — unchanged
- `surveys` **CHANGED**
  - `free_text_intent` — Stage 1 optional background blurb (semantics shifted from v1's "interest expression")
  - `background_json` — Stage 1 per-domain selections: `{domains: [{key, subareas, relationship}]}`; canonical sub-area + relationship vocabulary lives in [web/lib/surveyDomains.ts](../web/lib/surveyDomains.ts)
  - `node_ratings_json` — `{node_slug: "refresh"}` for Stage 2 foundation tile marks; unmarked tiles produce no entry
  - `pending_interests_json` — `{tile_slugs, free_text}` from Stage 3, cleared once `user_interests` rows are written by Stage 4
  - `comfort_responses_json` — populated by Stage 5 concept tour responses
  - `mode_balance` — float 0.0 to 1.0
  - `completed_stages` — TEXT[], ordered list of stages the user has finished; drives the route-per-stage gate
  - `updated_at`

### Graph (replaces canonical_topics / canonical_edges)

- `nodes` **NEW** (unified table for foundation + interest nodes)
  - `id`, `slug`, `title`, `description_md`, `domain` (math / physics / applied),
  - `kind` (foundation / interest)
  - `difficulty_hint` (intro / core / advanced)
  - `subtopics_json`
  - `unlocks_text` (short string for the "unlocks: X, Y, Z" line)
  - `pool_status` (active / deprecated)
  - `created_by_user_id` (null for foundations; user id for interests)
  - `created_at`, `updated_at`
- `edges` **NEW**
  - `id`, `source_node_id`, `target_node_id`
  - `edge_kind` (prerequisite / related)
  - `weight` (float)
  - `created_at`
- `edge_descriptions` **NEW** (Phase 10-rev §6 revision)
  - `edge_id` (PK, FK to `edges.id` ON DELETE CASCADE)
  - `description_md` — 3-5 sentence paragraph naming the specific concepts that bridge from source to target
  - `generated_at`, `generated_by_model`
  - Reused across users; first viewer of an edge pays for Haiku, subsequent clicks read the cache. Service-role-only; no end-user RLS policy.
- `user_node_states` **NEW**
  - `user_id`, `node_id`
  - `state` (unseen / bookmarked / active / struggling / comfortable)
  - `engagement_count`
  - `struggle_score` (float)
  - `last_engaged_at`
- `user_subtopic_states` **NEW** (Phase 10-rev §6)
  - `user_id`, `node_id`, `subtopic_slug` (PK on the triple)
  - `state` (familiar / refresh / new)
  - `updated_at`
  - Written by the concept tour (Stage 5) and read by the skill-tree NodePanel Subtopics section. Backfilled from `surveys.comfort_responses_json` at migration time.
- `user_interests` **NEW** (which interest nodes a user has actively claimed)
  - `id`, `user_id`, `node_id`, `weight` (float),
  - `added_via` (survey / explicit_request / cross_pollination)
  - `intent_context` (text, required) — soft text from the add-interest
    dialog capturing the resolved path and intent; read by the problem
    generator and the curriculum curator
  - `created_at`
- `curation_proposals` **NEW**
  - `id`, `kind` (merge / split / rename / promote / demote / add_edge / deprecate)
  - `payload_json` (details of the proposal)
  - `status` (pending / approved / rejected / applied)
  - `proposed_at`, `decided_at`, `decided_by`
- `megagraph_snapshots` **NEW**
  - `id`, `label`, `snapshot_json` (full graph state),
  - `taken_at`, `taken_by` (system / operator)

### Queue (NEW)

- `queue_items` **NEW**
  - `id`, `user_id`
  - `kind` (problem / paper_engagement / refresher / concept_review / suggested_interest)
  - `ref_id` (FK to underlying object; type-polymorphic by kind)
  - `state` (pending / surfaced / in_progress / done / skipped / dismissed / deferred)
  - `priority_score` (float)
  - `time_estimate_minutes_low`, `time_estimate_minutes_high`
  - `added_reason` (short text shown as "why this")
  - `parent_queue_item_id` (nullable; FK to `queue_items.id` ON DELETE SET NULL) — lineage marker set when a `concept_review` or `refresher` is created from inside another surface (e.g. clicking an orienting-concept term while reading a paper). Drives the reading view's back-link. Phase 10-rev §5.5.
  - `added_at`, `updated_at`, `deferred_at`
- `surfaced_picks` **NEW**
  - `id`, `user_id`, `queue_item_ids[]` (array of 3),
  - `surfaced_at`, `replaced_at`, `chosen_item_id`

### Problems

- `problems` **CHANGED** (carries forward; renamed FK)
  - existing fields preserved
  - `topic_node_id` (replaces `canonical_topic_id`; FK to `nodes`)
  - `version`, `previous_version_id` (immutability with versioning)
  - `tags` (text array)
  - `paper_id` (nullable; non-null marks paper-tied)
  - `pool_status` (active / retired / flagged)
  - `time_estimate_minutes_low`, `time_estimate_minutes_high`
  - `context_md` (the connective-tissue context paragraph)
- `problem_hints` — adds `part_label` (nullable text, migration 20250032):
  the part(s) a hint addresses ("Part (c)", "Parts (a)–(b)", "Whole problem"),
  rendered as a chip so the user can tell which part a hint speaks to (Phase
  10.5-rev Step 3, d10). Generation emits it per hint; the Haiku reformat
  backfill (`scripts/reformat_problems.py`) populates existing rows.
- `context_hooks` — unchanged in schema. Reframed as a content source
  for the problem generator. Hook seed data preserved.

### Papers

- `papers` **NEW** (global, shared across users)
  - `id`, `title`, `authors_json`, `year`,
  - `arxiv_id` (nullable, unique if present),
  - `doi` (nullable, unique if present),
  - `external_url`, `abstract_md`, `created_at`
  - `topic_node_ids` (uuid[], migration 20250033): the graph node(s) a paper
    is about, so a paper engagement queue card can show its topic (Phase
    10.5-rev Step 3, d22). Populated by `/propose-papers` (the model maps each
    paper to the user's interest titles → node ids); intrinsic to the subject,
    so stored per-paper and shared/unioned across users.
- `paper_engagements` **NEW** (per-user)
  - `id`, `user_id`, `paper_id`,
  - `why_this_md`,
  - `orienting_concepts_json` — `[{term, definition_md}]` since Phase 10-rev §5.2/5.3; legacy rows may still store `string[]` and are tolerated read-side by the UI,
  - `questions_json`,
  - `state`, `current_question_index`,
  - `created_at`, `updated_at`, `completed_at`
- `paper_answers` **NEW**
  - `id`, `engagement_id`, `question_id`,
  - `user_response_md`, `claude_response_md`, `submitted_at`
- `paper_qa` **NEW** (free-form Q&A)
  - `id`, `engagement_id`, `turn_index`,
  - `user_message_md`, `claude_response_md`, `created_at`

### Notebook

- `notebook_entries` **NEW**
  - `id`, `user_id`,
  - `entry_kind` (problem_attempt / paper_engagement / concept_review)
  - `ref_id` — points at `attempts.id` / `paper_engagements.id` / `nodes.id` respectively
  - `title`, `topic_node_slugs[]`,
  - `created_at`, `updated_at`
  - Full-text index for search.
  - `concept_review` rows added Phase 10-rev §5.5: written when the user marks "I've looked through this"; renders the cached brief from `node_concept_briefs` (which is keyed by the same `ref_id` value).
- `node_concept_briefs` **NEW** (Phase 10-rev §5.5)
  - `node_id` (PK, FK to `nodes.id` ON DELETE CASCADE)
  - `brief_md` — ~250-word warm orientation in three short paragraphs
  - `subtopic_glosses_json` — `[{slug, title, gloss_md}]`
  - `generated_at`, `generated_by_model`
  - Reused across users — first user to land on a node pays for Haiku, every subsequent user gets the cached row. Service-role-only; no end-user RLS policy.

### Attempts

- `attempts` **CHANGED**
  - existing fields preserved
  - `marked_refreshed` (bool)
  - `requested_easier`, `requested_harder` (bool)
  - `requested_assume_less` (bool) — per-attempt "explain more / assume less" signal
  - `parent_attempt_id` (nullable, links sibling attempts)

### User state and bookmarks

- `bookmarks` **NEW**
  - `id`, `user_id`,
  - `kind` (node / paper / problem / concept),
  - `ref_id_or_text`,
  - `created_at`, `promoted_at`
- `refresher_schedule` **NEW**
  - `id`, `user_id`,
  - `subject_kind` (attempt / engagement / concept),
  - `subject_ref_id`, `due_at`, `surfaced_at`

### Deprecated

- `canonical_topics`, `canonical_edges`, `user_plans`, `plan_nodes`,
  `daily_assignments`, `pending_topic_requests` — **DROPPED** in
  [migration 20250016](../supabase/migrations/20250016_drop_deprecated_tables.sql).
  All application code references removed in earlier migrations.

### Cost / observability

- `llm_calls` — unchanged.

## Key flows

### Adding an interest

A two-call dialog used both at onboarding (survey Stage 4) and during
daily use. Full specification:
[docs/survey-and-difficulty-design.md §2](survey-and-difficulty-design.md).

1. Next.js → Python `/add-interest/parse` with the user's free-text
   input and their user_id. Read-only.
2. Python pre-filters candidate nodes by title-similarity (cheap) and
   calls Haiku. Haiku:
   - splits the input into one or more distinct interest **segments**
     (e.g. "quantum mechanics and thermodynamics" → 2 segments),
   - classifies each as `specific` or `ambiguous`,
   - infers the implicit intent dial (teach / refresh / consolidate),
   - dedups each segment against the megagraph candidates (same /
     related / new),
   - returns mirror-back text, an optional follow-up prompt for
     specific segments, and 3–5 path options for ambiguous ones.
3. The client renders the mirror-back. The user optionally tells the
   system more (specific) or selects one or more paths (ambiguous).
4. Next.js → Python `/add-interest/resolve` once per segment, with the
   synthesized `final_intent_text`, the soft `intent_context` to
   persist, and at most one of `existing_node_slug` (verdict=same) or
   `related_node_slug` (verdict=related).
5. Python writes the `user_interests` row (with `intent_context`).
   When generating a new node it calls Sonnet, which also returns an
   `entry_point_preview_md` sentence used in the starter-preview
   string the UI shows.
6. The response carries a 6–10 tile **concept tour** — subtopic-level
   tiles drawn from the node's prerequisite foundation nodes — for the
   client to render as Stage 5 of the survey.
7. Downstream follow-ups (prerequisite refreshers, starter
   problem/paper) are queued by the curriculum curator's daily plan,
   not by `/add-interest/resolve` itself.

### Surfacing the daily three

1. User opens daily page.
2. Frontend → `/api/queue`.
3. Backend fetches the most recent unconsumed `surfaced_picks` row, or
   triggers a new surfacing.
4. Surfacing logic (deterministic, no LLM): pick three queue items with
   varied `kind` and time range when possible, prioritising in-progress
   paper engagements and due refreshers.

### Generating a problem

Pool-first:

1. Try existing `problems` matching `topic_node_id`, difficulty, not
   previously attempted by this user.
2. If hit: link via `queue_items.ref_id`.
3. If miss: Python `/generate-problem` with the node, user state, and
   optional context hook shortlist.
4. Persist new problem to pool. Link.

Background top-up runs daily across active nodes.

### Generating a paper engagement

1. Triggered when a paper enters a user's queue.
2. Lookup/insert into `papers` (dedupe by arxiv_id / doi / title).
3. Python `/generate-paper-engagement` with paper metadata, user
   interests, recent work. Returns why_this, orienting concepts,
   engagement questions.
4. Insert `paper_engagements` row. Link.

### Engaging with a problem

1. State → `in_progress`. Optional easier/harder sibling generated.
2. Upload solution photo via signed URL.
3. `/parse-solution` → markdown+LaTeX.
4. User reviews/edits the parse.
5. `/grade-solution` → grade + dialogic feedback.
6. Persist `attempts`. Create `notebook_entries`. `/assess-engagement`
   (Haiku) updates `user_node_states` and may queue an immediate
   follow-up (reinforcement / accelerate / prerequisite refresher).

### Engaging with a paper

1. State → `in_progress`.
2. User reads externally, returns, answers questions.
3. Each answer → `/grade-paper-answer` → conversational reply. Persist
   `paper_answers`.
4. Optional Q&A loop via `/paper-question`. Persist `paper_qa`.
5. State → `done`. Create `notebook_entries`. `/assess-engagement` runs
   for logging (paper engagements don't carry `topic_node_id`, so node
   state writes are skipped).

Engagements are multi-session: resuming uses `current_question_index`.

### Cross-pollination

Daily background job, after first weekly curation has completed:

1. For each active user, compute frontier (megagraph nodes 1–2 hops from
   their engaged set, not in their engaged set or bookmarks).
2. Rank by edge weight + count of other users engaged with the candidate.
3. Pick top candidate if score above threshold.
4. Insert `queue_items` of kind `suggested_interest` with one-week
   cooldown for similar suggestions.

### Weekly curation

Weekly background job:

1. Snapshot recent megagraph changes.
2. Python `/generate-curation-report` calls Sonnet with the changes and
   aggregate engagement signals.
3. Sonnet returns proposals (merges, splits, renames, etc.).
4. Persist as `curation_proposals`.
5. Operator reviews via admin UI; approves/rejects.
6. Approved proposals applied; new `megagraph_snapshots` row taken.

## Migration from v1

What survives unchanged in code or schema:

- `users`, `attempts` (with field additions), `problems` (with field
  additions), `problem_hints`, `context_hooks`, `llm_calls`.
- All Next.js auth, storage, basic CRUD code.
- The FastAPI service scaffold and existing `/generate-problem`,
  `/parse-solution` endpoints.
- Seed data for `context_hooks` (30 entries).

What is replaced via migration:

- `canonical_topics` and `canonical_edges` → `nodes` and `edges`. The
  21 v1 topics are split:
  - 13 become foundation nodes (see foundation list in
    `docs/graph-design.md`).
  - 8 become interest nodes (PDEs, real analysis, complex analysis,
    Lagrangian mechanics, special relativity, E&M II, optics, QM II).
  - Existing edges are translated, with edges referencing surviving
    nodes preserved and edges into demoted nodes reclassified.
- `surveys` columns adjusted per Data Model section.

What is deprecated:

- `user_plans`, `plan_nodes`, `daily_assignments`, `canonical_topics`,
  `canonical_edges`, `pending_topic_requests` — dropped in
  [migration 20250016](../supabase/migrations/20250016_drop_deprecated_tables.sql).

The migration is one SQL file plus a data-migration script. Since the
project is pre-launch with no real user data, no live-data preservation
is required beyond preserving the seed.

## Cost controls

Unchanged in mechanism from v1.

Expected monthly cost at 10 active users: $40–100. Higher than v1 due to
paper engagements being more expensive per call. Cost-sensitive routes
to monitor: paper engagement generation, paper Q&A, weekly curation
report. Cheap routes: deduplication checks (Haiku), surfacing (no LLM).

## Build phases (revised)

### Carries forward from v1 work

- Phase 1: Next.js skeleton, Supabase, magic-link auth, photo upload.
- Phase 2: canonical_topics + canonical_edges seeded (will be migrated
  in Phase 4-rev).
- Phase 3: FastAPI service scaffold, problems schema, context_hooks
  seeded, `/generate-problem` endpoint.
- Phase 4 step 1: solution upload + initial parsing.

### Phase 4-rev — Graph migration and queue foundation

- Migration: introduce `nodes`, `edges`, `user_node_states`,
  `user_interests`, `queue_items`, `surfaced_picks`, `bookmarks`,
  `curation_proposals`, `megagraph_snapshots`. Translate v1 data.
  Deprecate v1 plan tables.
- Update existing tables (`problems`, `attempts`, `surveys`).
- Implement `/add-interest` with dedup and generation.
- New survey UI (free-text intent, node exploration, comfort, mode
  balance).
- Queue surfacing endpoint and `/api/queue`.
- Daily-three page (mocked content acceptable to validate layout).

**Deliverable:** new user signs up, completes new survey, gets initial
interest nodes added to megagraph, sees a daily three (mocked).

### Phase 5-rev — Skill tree view and graph-driven content

- Skill tree view (user-facing): React Flow + Dagre, user's slice +
  adjacent regions, click-to-engage, state indicators.
- Connect existing problem flow (upload, parse, grade) to the queue and
  to graph state updates.
- "Mark as refreshed" path.
- Notebook entry creation for problem attempts.
- Notebook browse and read UI.

**Deliverable:** real problem flow works; users can see and explore
their skill tree.

### Phase 6-rev — Paper engagement

- `papers` table and dedup.
- `/generate-paper-engagement`.
- Paper engagement UI: why-this, concepts, link, questions, multi-session
  resume.
- `/grade-paper-answer` with dialogic feedback.
- Free-form Q&A turns.
- Notebook entries for paper engagements.
- `/suggest-papers` background job.

**Deliverable:** full paper loop including system-suggested papers.

### Phase 7-rev — Adaptation, refreshers, cross-pollination

- `/assess-engagement` (Haiku) after attempts and engagements;
  `/plan-queue` (Sonnet) daily per active user; `/check-deferred`
  (deterministic) re-queues deferred items when prerequisites land. Replaces
  the placeholder `/update-queue`.
- `user_node_states` recomputation.
- Refresher scheduling and surfacing.
- Explicit request flow.
- Cross-pollination job (becomes active after first weekly curation).

**Deliverable:** queue feels responsive; megagraph quietly drives
discovery.

### Phase 8-rev — Weekly curation and operator surfaces

- `/generate-curation-report` weekly job.
- Operator admin UI: review proposals, approve/reject, apply.
- Operator megagraph view (functional version): full graph render with
  layer toggles and time scrubber.
- Snapshot management.
- Cost dashboard.

**Deliverable:** operator can run curation; megagraph is maintainable.

### Phase 9-rev — Polish

- Design system pass.
- Mobile polish.
- Error monitoring.

**Deliverable:** v2 ready for friends.

### Deferred (v2.1+)

- Live arXiv search and ingestion.
- Bespoke D3 megagraph visualisation (portfolio piece).
- Calendar view in notebook.
- Return-after-absence prompts.
- BYO API key.
- Notebook export.
- Hand-authored problems.
- Per-user difficulty calibration.

## Risks and mitigations

| Risk                                                              | Mitigation                                                                |
|-------------------------------------------------------------------|---------------------------------------------------------------------------|
| Deduplication makes bad merges silently                            | Operator catches in weekly curation; merges are reversible via snapshot   |
| Weekly curation becomes a chore                                    | Report is sortable and bulk-actionable; aim for 15–30 min/week            |
| Megagraph grows in unhelpful directions                            | Curation includes "deprecate" and "demote" proposals; not just additions  |
| Cross-pollination feels noisy or random                            | Threshold + cooldown + opt-out; surfaces at most once per user per week   |
| Paper engagements cost more than expected                          | Cap Q&A turns; monitor cost-per-engagement; tune prompts                  |
| Cold start: megagraph is sparse for weeks                          | Cross-pollination doesn't activate until after first curation round       |
| Migration mistakes corrupt the graph                               | Pre-launch project (no user data); snapshot before migration; reversible  |
| Skill tree view doesn't feel like a video game                     | Treat as a real design task; iterate on visuals; not "list with icons"    |
