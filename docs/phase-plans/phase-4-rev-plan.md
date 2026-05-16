# Phase 4-rev — execution plan

Forward-looking plan for the multi-session Phase 4-rev build. Source-of-truth
for the product is [../SPEC.md](../SPEC.md), [../ARCHITECTURE.md](../ARCHITECTURE.md),
[../graph-design.md](../graph-design.md), and [../personas.md](../personas.md);
this file captures *execution* decisions and step ordering. Mirrors the shape of
[../archive/phase-3-plan.md](../archive/phase-3-plan.md) — decisions are flagged
so they can be confirmed or overridden before execution.

## Where we are

- **Phases 1–3**: done. End-to-end: a user with an approved plan opens `/daily`
  and gets an AI-generated problem with hints + historical context, cached by
  `(canonical_topic_id, difficulty, context_hook_id)`. See
  [../archive/phase-3-plan.md](../archive/phase-3-plan.md).
- **v1 Phase 4 (vision parsing)**: migration `20250007_phase4_attempts.sql`
  was written but **never applied**. The FastAPI route and upload-page rewrite
  were never started. That work is now superseded by Phase 4-rev — see the
  "Decisions locked in" table below.
- **Product redesign**: SPEC, ARCHITECTURE, and graph model have been replaced.
  [../pivot-plan.md](../pivot-plan.md) documents the full reconciliation. This
  phase is the first execution slice of that pivot.
- **Phase 4-rev migrations (steps 1–6)**: all six migrations written and applied.
  Steps 7–13 (FastAPI routes, Next.js UI, code deletion) are next.

## Phase 4-rev goal

A new user signs up, completes the v2 survey (free-text intent + node ratings +
mode-balance slider), sees their interests added to the megagraph (with
autonomous deduplication), and lands on `/daily` to see three surfaced queue
items (mocked content acceptable). The v1 plan tables (`canonical_topics`,
`canonical_edges`, `user_plans`, `plan_nodes`, `daily_assignments`,
`pending_topic_requests`) are deprecated — no new writes. All old plan-flow
code is deleted.

Out of scope: vision parsing and real problem flow (Phase 5-rev); paper
engagement (Phase 6-rev); adaptation, refreshers, and cross-pollination
(Phase 7-rev).

## Decisions locked in

Worked through in the reconciliation session. Don't re-litigate.

| Decision | Choice | Why |
|---|---|---|
| Migration `20250007_phase4_attempts.sql` | **Never apply — abandon** | It was written for v1's `assignment_id`-anchored schema. Phase 4-rev step 4 (migration `20250011`) handles `attempts` in the correct v2 shape. Applying 20250007 first and then reversing it would create noise. |
| Migration strategy | **UUID-preserving seed copy** | Copy canonical_topics rows into nodes preserving their `id` values so `context_hooks.related_topic_ids uuid[]` survives without any rewrite. |
| `attempts.assignment_id` | **Drop outright** in step 4 | No live data; pre-launch. Replaced by `queue_item_id`. No nullable interim. |
| `surveys.mode_balance` direction | `0.0` = all problems, `1.0` = all papers | Matches the lexical order of `queue_items.kind`. |
| `problems.generated_context_md` | **Rename → `context_md`** in step 4 | Same column, cleaner name (follows `_json` / bare naming conventions used elsewhere). No second column added. |
| `pending_topic_requests` | **Deprecated** alongside other v1 plan tables | Functionally superseded by `/add-interest`. Added to step 6 deprecation list even though it isn't in CLAUDE.md's original deprecation list. |
| `nodes.subtopics` column name | `subtopics_json` (not `subtopics`) | Matches ARCHITECTURE.md's `_json` suffix convention for jsonb columns. |
| `nodes.slug` uniqueness | Unique constraint + collision → `curation_proposals` merge row | Prevents race-created duplicate nodes; operator cleans up via weekly curation. |
| `surfaced_picks.queue_item_ids[]` size | **Length ≤ 3 acceptable** | A fresh user after first survey may have fewer than 3 queue items. Surface 1 or 2 with a "more coming" placeholder rather than block surfacing entirely. |
| Daily-three content in acceptance test | **Mocked** | ARCHITECTURE.md's Phase 4-rev deliverable wording explicitly allows mocked content for the layout validation. Real content requires the full problem + paper flows from Phases 5-rev and 6-rev. |
| `/parse-solution` | **Deferred to Phase 5-rev** | Phase 4-rev is already large. The DB columns (`parsed_markdown`, `parse_status`, etc.) exist in 20250007 — they'll be added by migration 20250011 without 20250007 being applied. |
| Dedup autonomy | **No user confirmation** | Per CLAUDE.md §Key design constraints and graph-design.md §Deduplication: "Interest deduplication is autonomous." Operator catches mistakes in weekly curation. |
| `profiles.timezone` | Add `timezone text` column in step 1 | Needed by Phase 7-rev refresher surfacing; cheapest to add alongside the first graph migration rather than as a standalone later. |

**Deferred decision still open (F9):** `queue_items.ref_id` type-by-kind
mapping — for `kind='problem'` ref_id → `problems(id)`, for
`kind='suggested_interest'` ref_id → `nodes(id)`, but `kind='concept_review'`
target is unclear. Must be pinned before step 8 (`/surface-daily` +
`/update-queue` skeleton). See [../pivot-plan.md §F9](../pivot-plan.md).

## Step status

| # | Step | Status |
|---|---|---|
| 1 | Migration `20250008_graph_schema.sql` | Done |
| 2 | Migration `20250009_queue_schema.sql` | Done |
| 3 | Migration `20250010_papers_schema.sql` | Done |
| 4 | Migration `20250011_modify_problems_attempts_surveys.sql` | Done |
| 5+6 | Migration `20250012_seed_nodes_edges.sql` (combined seed + deprecation) | Done |
| — | Migration `20250013_surveys_rls.sql` (bug fix — see Deviations) | Done |
| 7 | FastAPI `POST /add-interest` | Done |
| 8 | FastAPI `POST /surface-daily` + `/update-queue` skeleton | Done |
| 9 | Next.js: new survey UI | Done |
| 10 | Next.js: queue read + interest API routes | Done |
| 11 | Next.js: daily-three page (mocked content) | Done |
| 12 | Delete deprecated code | Done |
| 13 | Phase 4-rev acceptance + status line update | Done |

Steps 1–6 are pure SQL — no code changes. Apply each with
`npx supabase db push --db-url <url>` and verify before moving to the next.

---

## Step 1 — `20250008_graph_schema.sql`

Creates the graph layer and supporting infrastructure. Also adds
`profiles.timezone`.

```sql
-- profiles: timezone for refresher surfacing (Phase 7-rev)
alter table public.profiles
  add column if not exists timezone text;

-- nodes: the unified two-layer graph
create table public.nodes (
  id                  uuid primary key default gen_random_uuid(),
  slug                text not null unique,
  title               text not null,
  description_md      text not null default '',
  domain              text not null check (domain in ('math','physics','applied')),
  kind                text not null check (kind in ('foundation','interest')),
  difficulty_hint     text not null check (difficulty_hint in ('intro','core','advanced')),
  subtopics_json      jsonb not null default '[]',
  unlocks_text        text,
  pool_status         text not null default 'active' check (pool_status in ('active','deprecated')),
  created_by_user_id  uuid references public.profiles(id) on delete set null,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index nodes_kind_idx       on public.nodes (kind);
create index nodes_domain_idx     on public.nodes (domain);
create index nodes_pool_status_idx on public.nodes (pool_status);

-- edges: prerequisite and related relationships between nodes
create table public.edges (
  id              uuid primary key default gen_random_uuid(),
  source_node_id  uuid not null references public.nodes(id) on delete cascade,
  target_node_id  uuid not null references public.nodes(id) on delete cascade,
  edge_kind       text not null check (edge_kind in ('prerequisite','related')),
  weight          real not null default 1.0,
  created_at      timestamptz not null default now(),
  unique (source_node_id, target_node_id)
);

create index edges_source_idx on public.edges (source_node_id);
create index edges_target_idx on public.edges (target_node_id);

-- user_node_states: per-user engagement state for each node
create table public.user_node_states (
  user_id          uuid not null references public.profiles(id) on delete cascade,
  node_id          uuid not null references public.nodes(id) on delete cascade,
  state            text not null default 'unseen'
                     check (state in ('unseen','bookmarked','active','struggling','comfortable')),
  engagement_count integer not null default 0,
  struggle_score   real not null default 0.0,
  last_engaged_at  timestamptz,
  primary key (user_id, node_id)
);

create index user_node_states_user_idx on public.user_node_states (user_id);

-- user_interests: which interest nodes a user has claimed
create table public.user_interests (
  id        uuid primary key default gen_random_uuid(),
  user_id   uuid not null references public.profiles(id) on delete cascade,
  node_id   uuid not null references public.nodes(id) on delete cascade,
  weight    real not null default 1.0,
  added_via text not null check (added_via in ('survey','explicit_request','cross_pollination')),
  created_at timestamptz not null default now(),
  unique (user_id, node_id)
);

create index user_interests_user_idx on public.user_interests (user_id);

-- bookmarks
create table public.bookmarks (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles(id) on delete cascade,
  kind          text not null check (kind in ('node','paper','problem','concept')),
  ref_id_or_text text not null,
  created_at    timestamptz not null default now(),
  promoted_at   timestamptz
);

create index bookmarks_user_idx on public.bookmarks (user_id);

-- curation_proposals: operator-facing graph change proposals
create table public.curation_proposals (
  id           uuid primary key default gen_random_uuid(),
  kind         text not null
                 check (kind in ('merge','split','rename','promote','demote','add_edge','deprecate')),
  payload_json jsonb not null,
  status       text not null default 'pending'
                 check (status in ('pending','approved','rejected','applied')),
  proposed_at  timestamptz not null default now(),
  decided_at   timestamptz,
  decided_by   uuid references public.profiles(id) on delete set null
);

create index curation_proposals_status_idx on public.curation_proposals (status);

-- megagraph_snapshots: full graph state after each weekly curation
create table public.megagraph_snapshots (
  id            uuid primary key default gen_random_uuid(),
  label         text,
  snapshot_json jsonb not null,
  taken_at      timestamptz not null default now(),
  taken_by      text not null check (taken_by in ('system','operator'))
);

-- RLS
alter table public.nodes             enable row level security;
alter table public.edges             enable row level security;
alter table public.user_node_states  enable row level security;
alter table public.user_interests    enable row level security;
alter table public.bookmarks         enable row level security;
alter table public.curation_proposals enable row level security;
alter table public.megagraph_snapshots enable row level security;

-- nodes + edges: readable by all authenticated users; writable only by service role
create policy nodes_select_authenticated on public.nodes
  for select using (auth.role() = 'authenticated');
create policy edges_select_authenticated on public.edges
  for select using (auth.role() = 'authenticated');

-- per-user tables: gate on user_id
create policy user_node_states_own on public.user_node_states
  for all using (auth.uid() = user_id);
create policy user_interests_own on public.user_interests
  for all using (auth.uid() = user_id);
create policy bookmarks_own on public.bookmarks
  for all using (auth.uid() = user_id);

-- curation and snapshots: operator-only (no RLS policy = service role only)
```

**Verify after apply:** `\d public.nodes` shows all columns; `select count(*) from public.nodes` returns 0; `\d public.profiles` shows `timezone` column.

---

## Step 2 — `20250009_queue_schema.sql`

```sql
create table public.queue_items (
  id                          uuid primary key default gen_random_uuid(),
  user_id                     uuid not null references public.profiles(id) on delete cascade,
  kind                        text not null
                                check (kind in ('problem','paper_engagement','refresher',
                                                'concept_review','suggested_interest')),
  ref_id                      uuid,
  state                       text not null default 'pending'
                                check (state in ('pending','surfaced','in_progress',
                                                 'done','skipped','dismissed')),
  priority_score              real not null default 0.0,
  time_estimate_minutes_low   smallint,
  time_estimate_minutes_high  smallint,
  added_reason                text,
  added_at                    timestamptz not null default now(),
  updated_at                  timestamptz not null default now()
);

create index queue_items_user_state_idx on public.queue_items (user_id, state);
create index queue_items_user_priority_idx on public.queue_items (user_id, priority_score desc);

create table public.surfaced_picks (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles(id) on delete cascade,
  queue_item_ids   uuid[] not null,   -- length 1–3; see pivot-plan §F8
  surfaced_at      timestamptz not null default now(),
  replaced_at      timestamptz,
  chosen_item_id   uuid references public.queue_items(id) on delete set null
);

create index surfaced_picks_user_idx on public.surfaced_picks (user_id);

create table public.refresher_schedule (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles(id) on delete cascade,
  subject_kind    text not null check (subject_kind in ('attempt','engagement','concept')),
  subject_ref_id  uuid not null,
  due_at          timestamptz not null,
  surfaced_at     timestamptz
);

create index refresher_schedule_user_due_idx on public.refresher_schedule (user_id, due_at);

-- RLS
alter table public.queue_items        enable row level security;
alter table public.surfaced_picks     enable row level security;
alter table public.refresher_schedule enable row level security;

create policy queue_items_own on public.queue_items
  for all using (auth.uid() = user_id);
create policy surfaced_picks_own on public.surfaced_picks
  for all using (auth.uid() = user_id);
create policy refresher_schedule_own on public.refresher_schedule
  for all using (auth.uid() = user_id);
```

**Note on `queue_items.ref_id`:** the column is untyped (`uuid`, nullable) because it's polymorphic by `kind`. The full kind→table mapping is pinned in [../pivot-plan.md §F9](../pivot-plan.md) before step 8 — don't start step 8 until that decision is recorded there.

---

## Step 3 — `20250010_papers_schema.sql`

```sql
create table public.papers (
  id           uuid primary key default gen_random_uuid(),
  title        text not null,
  authors_json jsonb not null default '[]',
  year         smallint,
  arxiv_id     text unique,
  doi          text unique,
  external_url text unique,
  abstract_md  text,
  created_at   timestamptz not null default now()
);

create table public.paper_engagements (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid not null references public.profiles(id) on delete cascade,
  paper_id                uuid not null references public.papers(id) on delete cascade,
  why_this_md             text,
  orienting_concepts_json jsonb not null default '[]',
  questions_json          jsonb not null default '[]',
  -- questions_json shape: [{id: uuid, kind: 'comprehension'|'critical'|'connective',
  --                         prompt_md: text, order: int}]
  state                   text not null default 'pending'
                            check (state in ('pending','in_progress','completed')),
  current_question_index  smallint not null default 0,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  completed_at            timestamptz
);

create index paper_engagements_user_idx on public.paper_engagements (user_id);

create table public.paper_answers (
  id                uuid primary key default gen_random_uuid(),
  engagement_id     uuid not null references public.paper_engagements(id) on delete cascade,
  question_id       uuid not null,   -- references questions_json[].id
  user_response_md  text,
  claude_response_md text,
  submitted_at      timestamptz
);

create table public.paper_qa (
  id                  uuid primary key default gen_random_uuid(),
  engagement_id       uuid not null references public.paper_engagements(id) on delete cascade,
  turn_index          smallint not null,
  user_message_md     text not null,
  claude_response_md  text,
  created_at          timestamptz not null default now()
);

create table public.notebook_entries (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.profiles(id) on delete cascade,
  entry_kind          text not null check (entry_kind in ('problem_attempt','paper_engagement')),
  ref_id              uuid not null,
  title               text not null,
  topic_node_slugs    text[] not null default '{}',
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  fts_vector          tsvector generated always as (
                        to_tsvector('english', coalesce(title,'') || ' ' ||
                        array_to_string(topic_node_slugs,' '))
                      ) stored
);

create index notebook_entries_user_idx on public.notebook_entries (user_id);
create index notebook_entries_fts_idx  on public.notebook_entries using gin (fts_vector);

-- RLS
alter table public.papers            enable row level security;
alter table public.paper_engagements enable row level security;
alter table public.paper_answers     enable row level security;
alter table public.paper_qa          enable row level security;
alter table public.notebook_entries  enable row level security;

create policy papers_select_authenticated on public.papers
  for select using (auth.role() = 'authenticated');
create policy paper_engagements_own on public.paper_engagements
  for all using (auth.uid() = user_id);
create policy paper_answers_own on public.paper_answers
  for all using (
    auth.uid() = (select user_id from public.paper_engagements
                  where id = engagement_id)
  );
create policy paper_qa_own on public.paper_qa
  for all using (
    auth.uid() = (select user_id from public.paper_engagements
                  where id = engagement_id)
  );
create policy notebook_entries_own on public.notebook_entries
  for all using (auth.uid() = user_id);
```

---

## Step 4 — `20250011_modify_problems_attempts_surveys.sql`

The big one. Applies all column-level changes from [../pivot-plan.md §B](../pivot-plan.md).

```sql
-- ── problems ────────────────────────────────────────────────────────────────

-- Rename canonical_topic_id → topic_node_id. FK target stays uuid for now;
-- the actual FK is added in step 5 once nodes rows exist.
alter table public.problems
  rename column canonical_topic_id to topic_node_id;

-- Rename generated_context_md → context_md (same column, cleaner name)
alter table public.problems
  rename column generated_context_md to context_md;

alter table public.problems
  add column version               smallint not null default 1,
  add column previous_version_id   uuid references public.problems(id),
  add column tags                  text[] not null default '{}',
  add column paper_id              uuid references public.papers(id),
  add column pool_status           text not null default 'active'
                                     check (pool_status in ('active','retired','flagged')),
  add column time_estimate_minutes_low  smallint,
  add column time_estimate_minutes_high smallint;

-- Rewrite cache-key partial indexes to use topic_node_id and exclude paper-tied
-- problems (paper-tied problems aren't pool-reusable per CLAUDE.md).
drop index if exists problems_cache_key_with_hook;
drop index if exists problems_cache_key_no_hook;

create unique index problems_cache_key_with_hook on public.problems
  (topic_node_id, difficulty, context_hook_id)
  where context_hook_id is not null and paper_id is null;

create unique index problems_cache_key_no_hook on public.problems
  (topic_node_id, difficulty)
  where topic_node_id is not null and context_hook_id is null and paper_id is null;

-- ── attempts ────────────────────────────────────────────────────────────────

-- Drop the v1 assignment coupling. No live data — safe to drop outright.
alter table public.attempts
  drop constraint if exists attempts_one_per_assignment;

alter table public.attempts
  drop column assignment_id;

alter table public.attempts
  add column queue_item_id      uuid references public.queue_items(id),
  add column marked_refreshed   boolean not null default false,
  add column requested_easier   boolean not null default false,
  add column requested_harder   boolean not null default false,
  add column parent_attempt_id  uuid references public.attempts(id),
  add column grade_response_md  text,
  add column disputed           boolean not null default false;

-- ── surveys ──────────────────────────────────────────────────────────────────

alter table public.surveys
  drop column if exists background_json,
  drop column if exists topic_states_json,
  drop column if exists difficulty_curve;

alter table public.surveys
  add column free_text_intent      text,
  add column node_ratings_json     jsonb not null default '{}',
  add column comfort_responses_json jsonb not null default '{}',
  add column mode_balance          real not null default 0.0
                                     check (mode_balance between 0.0 and 1.0),
  add column updated_at            timestamptz not null default now();
```

**Important:** Do not apply migration `20250007_phase4_attempts.sql`. It predates the redesign and conflicts with the `assignment_id` drop above. It was written but never applied — leave it in place as history but skip it in the push sequence.

---

## Step 5 — `20250012_seed_nodes_edges.sql`

Copies the v1 canonical seed into the new graph tables, preserving UUIDs so
`context_hooks.related_topic_ids` continues to resolve.

```sql
-- Copy canonical_topics → nodes, preserving IDs.
-- 13 rows become foundation nodes; 8 become interest nodes.
insert into public.nodes
  (id, slug, title, description_md, domain, kind, difficulty_hint, subtopics_json, created_at)
select
  id,
  slug,
  title,
  coalesce(description, ''),
  domain,
  case when slug in (
    'calculus-1','calculus-2','multivariable-calculus','linear-algebra','odes',
    'probability','statistics',
    'classical-mechanics','waves-oscillations','electromagnetism-1',
    'thermodynamics','statistical-mechanics','quantum-mechanics-1'
  ) then 'foundation' else 'interest' end,
  difficulty_band,   -- difficulty_band → difficulty_hint (same values)
  coalesce(subtopics, '[]'::jsonb),
  created_at
from public.canonical_topics
on conflict (id) do nothing;

-- Copy canonical_edges → edges (all are prerequisite edges in v1).
insert into public.edges
  (source_node_id, target_node_id, edge_kind, weight)
select
  prerequisite_topic_id,
  dependent_topic_id,
  'prerequisite',
  weight::real
from public.canonical_edges
on conflict (source_node_id, target_node_id) do nothing;

-- Update problems.topic_node_id FK now that nodes rows exist.
-- (The column was renamed in step 4; values are already the correct UUIDs.)
alter table public.problems
  add constraint problems_topic_node_id_fkey
  foreign key (topic_node_id) references public.nodes(id);
```

**Verify:** `select kind, count(*) from nodes group by kind` should return
`foundation | 13` and `interest | 8`. `select count(*) from edges` should
return 28.

---

## Step 6 — `20250013_deprecate_v1_tables.sql`

Locks out writes without dropping — preserves seed history for operator
introspection. Physical drops land in Phase 8-rev step 6.

```sql
comment on table public.canonical_topics   is 'DEPRECATED — superseded by nodes. No new writes. Drop in Phase 8-rev.';
comment on table public.canonical_edges    is 'DEPRECATED — superseded by edges. No new writes. Drop in Phase 8-rev.';
comment on table public.user_plans         is 'DEPRECATED — superseded by queue_items. No new writes. Drop in Phase 8-rev.';
comment on table public.plan_nodes         is 'DEPRECATED — superseded by queue_items. No new writes. Drop in Phase 8-rev.';
comment on table public.daily_assignments  is 'DEPRECATED — superseded by surfaced_picks. No new writes. Drop in Phase 8-rev.';
comment on table public.pending_topic_requests is 'DEPRECATED — superseded by /add-interest. No new writes. Drop in Phase 8-rev.';

-- Revoke INSERT and UPDATE from the anon and authenticated roles.
-- Service role retains access for operator introspection.
revoke insert, update on public.canonical_topics       from anon, authenticated;
revoke insert, update on public.canonical_edges        from anon, authenticated;
revoke insert, update on public.user_plans             from anon, authenticated;
revoke insert, update on public.plan_nodes             from anon, authenticated;
revoke insert, update on public.daily_assignments      from anon, authenticated;
revoke insert, update on public.pending_topic_requests from anon, authenticated;
```

---

## Step 7 — FastAPI `POST /add-interest`

The core new endpoint. Implements the dedup + generate flow from
[../graph-design.md](../graph-design.md) §Deduplication.

New files:
- `api/routes/add_interest.py`
- `api/prompts/add_interest.py`

**Request schema** (in `api/schemas.py`):

```python
class AddInterestRequest(BaseModel):
    user_id: UUID
    raw_text: str           # free-text interest expression
    added_via: str          # 'survey' | 'explicit_request'

class DeduplicationVerdict(BaseModel):
    """Haiku dedup call output."""
    verdict: str            # 'same' | 'related' | 'new'
    matched_node_slug: str | None = None
    reason: str | None = None

class GeneratedInterestNode(BaseModel):
    """Sonnet node-generation call output."""
    title: str
    slug: str               # kebab-case, lowercase, ASCII
    description_md: str
    domain: str             # 'math' | 'physics' | 'applied'
    difficulty_hint: str    # 'intro' | 'core' | 'advanced'
    subtopics: list[str]    # display names, not slugs
    proposed_prerequisite_slugs: list[str]

class AddInterestResponse(BaseModel):
    node_id: UUID
    node_slug: str
    verdict: str            # 'same' | 'related' | 'new'
    user_interest_id: UUID
```

**Flow:**

1. Load all existing `nodes` (titles, slugs, descriptions) as candidate list.
   Pre-filter to a title-similarity shortlist (simple `lower(title)`
   trigram or substring match) to keep the Haiku prompt bounded. Cap at 20
   candidates.

2. **Haiku dedup call** with the shortlist:
   - System: "You are deduplicating a user interest against an existing graph.
     Return JSON: `{verdict, matched_node_slug, reason}`. Verdict options:
     `same` (the user's interest IS this node), `related` (adjacent but
     distinct — suggest the closest slug), `new` (no match)."
   - User: "User expressed interest in: `{raw_text}`. Candidate nodes: `[{slug, title, description}]`."
   - Logged to `llm_calls` as route `'add-interest/dedup'`.

3. **Branch on verdict:**
   - `same`: write `user_interests` row linking to the matched node. Return.
   - `related` or `new`: proceed to Sonnet generation.

4. **Sonnet generation call** (if not `same`):
   - System: structured generation prompt — produce `title`, `slug`,
     `description_md`, `domain`, `difficulty_hint`, `subtopics[]`,
     `proposed_prerequisite_slugs[]`. Slug must be unique (checked against
     existing slugs passed in the prompt). Logged as route
     `'add-interest/generate'`.

5. **Insert node** with `INSERT ... ON CONFLICT (slug) DO NOTHING`, then
   re-select. If the conflict fires (race between two simultaneous adds),
   insert a `curation_proposals` row with `kind='merge'` and
   `payload_json={slug, new_title, raw_text}` and link the user to the
   existing node.

6. **Insert edges** from `proposed_prerequisite_slugs` (translate slugs →
   node ids; skip any slug that doesn't exist rather than erroring).

7. **Write `user_interests` row.**

8. Return `AddInterestResponse`.

**Prompts** (`api/prompts/add_interest.py`):

Keep system prompts short and cacheable. The dedup system prompt is
≤ ~200 tokens and doesn't change call-to-call — prompt cache applies.
The generation system prompt similarly. Pass the dynamic data (candidate list,
raw text, existing slugs) in the user message.

**Tests** (`api/tests/test_add_interest.py`): cover auth (401), Haiku
`same` verdict → no Sonnet call + user_interests written, Haiku `new` verdict
→ Sonnet called + node inserted + edges inserted, slug collision → race handled
→ curation_proposals row written, `related` verdict → new node with related-edge
to matched node.

---

## Step 8 — FastAPI `POST /surface-daily` + `/update-queue` skeleton

**Resolve F9 before starting this step.** Pin the full `queue_items.kind →
ref table` mapping in [../pivot-plan.md §F9](../pivot-plan.md).

### `POST /surface-daily`

Deterministic — no LLM call. Picks up to 3 varied items from the user's
pending queue and writes a `surfaced_picks` row.

Request: `{ user_id: UUID }`
Response: `{ pick_id: UUID, items: [{queue_item_id, kind, ref_id, added_reason, time_estimate_*}] }`

Selection rules:
1. Fetch all `queue_items` for user with `state='pending'`, order by
   `priority_score desc`.
2. Pick at most 3, trying to vary `kind` (don't surface three problems if a
   paper_engagement is available).
3. If fewer than 3 available, surface what exists (length ≤ 3 per decision
   above).
4. Set selected items' `state = 'surfaced'`. Write `surfaced_picks`.

### `POST /update-queue` (skeleton only)

In Phase 4-rev this is a no-op stub that returns `{ok: true}`. Real
implementation lands in Phase 7-rev. Stub it now so the Next.js survey handler
has a callable endpoint after onboarding.

---

## Step 9 — Next.js: new survey UI

Three files to rewrite, one new helper.

**`web/app/api/survey/route.ts`** — the survey save handler.

1. Validate auth, parse request body: `{ free_text_intent, node_ratings, comfort_responses, mode_balance }`.
2. Upsert `surveys` row (new shape).
3. For each node rated `"interested"` in `node_ratings`: call Python
   `/add-interest` via `addInterest()` in `web/lib/pythonApi.ts` with
   `added_via='survey'`. Run in sequence (parallel is fine for a small survey,
   but serial is easier to reason about for error handling).
4. For the free-text intent: extract potential interest expressions — the
   simplest approach is one `/add-interest` call with the full `free_text_intent`
   string. The Python side handles parsing.
5. Seed `user_node_states` rows for nodes rated `"comfortable"` or `"refresh"`
   (state = `'comfortable'` for comfortable; `'active'` for refresh — user is
   telling us they want to engage with it).
6. Call Python `/update-queue` (skeleton) to initialise the queue.
7. Redirect to `/daily`.

**`web/components/SurveyForm.tsx`** — multi-step form.

Steps:
1. **Intent** — large `<textarea>` for free-text interest expression. Prompt:
   "What do you want to learn or relearn? Write however feels natural — a few
   words or a few sentences."
2. **Node ratings** — show all 21 foundation + interest nodes (from a server
   fetch of `nodes`). Three toggle states per node: `interested` / `comfortable`
   / `refresh`. Unrated = skip. Foundation nodes shown first; interest nodes
   as a lighter secondary section.
3. **Mode balance** — a single slider from Problems to Papers (0.0–1.0). Default 0.5.
4. **Review** — summary of what they said; submit button.

Keep the form simple and honest — no progress bars, no gamification.

**`web/app/survey/page.tsx`** — server component wrapper that loads
`nodes` (for step 2), renders `<SurveyForm />` as a client component.

---

## Step 10 — Next.js: queue read + interest API routes

**`web/app/api/queue/route.ts`** (GET):
- Auth check; call Python `/surface-daily` if no current open `surfaced_picks`
  row exists (or all items in the current pick have been resolved).
- Return the surfaced items enriched with enough data for the daily-three card
  UI (title, kind, added_reason, time_estimate).

**`web/app/api/queue/reroll/route.ts`** (POST):
- Auth check; mark current `surfaced_picks.replaced_at = now()`; call
  `/surface-daily` again; return new items.

**`web/app/api/interest/route.ts`** (POST):
- Auth check; call Python `/add-interest` with `added_via='explicit_request'`;
  return the new/matched node details.

---

## Step 11 — Next.js: daily-three page (mocked content)

Rewrite `web/app/daily/page.tsx`. Mocked content is acceptable for this
phase — the layout and navigation must work, but cards can show placeholder
copy ("A problem on ODEs is waiting", "A paper on gravitational waves").

The page should:
- Load the user's current `surfaced_picks` via `/api/queue`.
- Render three cards (or 1–2 if fewer available, with a "more coming" state).
- Each card shows: kind badge, title/description, added_reason ("why this"),
  time estimate, and a primary CTA (stub links for now).
- A "reroll" link on the page → `POST /api/queue/reroll`.

Keep the previous `/daily` page's auth-redirect behaviour (unauthenticated →
`/signin`; no survey → `/survey`).

---

## Step 12 — Delete deprecated code

Once steps 9–11 pass a manual smoke test, delete the v1 plan-flow code that is
now unreachable:

| File | Action |
|---|---|
| `web/app/api/plan/approve/route.ts` | Delete |
| `web/app/api/plan/adjust/route.ts` | Delete |
| `web/app/plan/page.tsx` | Delete |
| `web/lib/plan.ts` | Delete |
| `web/lib/dailyAssignment.ts` | Delete (replaced by the queue helper in step 10) |
| `web/components/PlanGraph.tsx` | Delete |
| `web/components/SkillTree.tsx` | Delete |
| `web/components/SkillTreeView.tsx` | Delete |

Update `web/lib/types.ts` to remove `CanonicalTopic`, `CanonicalEdge`,
`UserPlan`, `PlanNode`, `TopicState`, `TopicStateMap`, `SurveyPayload`,
`DailyAssignment` and add v2 types (`Node`, `Edge`, `QueueItem`, `SurfacedPick`,
`UserNodeState`, `UserInterest`).

Run `npm run build` and `npm run lint` after deletions to catch any remaining
references.

---

## Step 13 — Phase 4-rev acceptance

End-to-end smoke test:

1. New user signs up via magic link.
2. Completes the v2 survey: writes a free-text intent, rates 2–3 nodes,
   sets a mode balance, submits.
3. Verify in Supabase: `surveys` row has correct shape; `user_interests` rows
   exist for rated nodes; `nodes` table has any newly-created interest nodes;
   `user_node_states` rows exist for rated nodes.
4. App redirects to `/daily`. Three cards render (mocked content OK).
5. Reroll works — cards change.
6. `llm_calls` has rows for the `/add-interest` dedup + generate calls with
   sane token counts.

Update the status line in [../pivot-plan.md](../pivot-plan.md):

```
Status: Phase 4-rev complete. Last commit: <hash>.
Next step: Phase 5-rev step 1 — POST /parse-solution.
```

---

## Risks to watch

- **UUID preservation in step 5.** If `canonical_topics.id` values for any
  reason don't copy cleanly (e.g., an index conflict), `context_hooks.related_topic_ids`
  will silently become dangling UUIDs. Verify with a post-migration check:
  `select count(*) from context_hooks ch cross join lateral unnest(ch.related_topic_ids) r(id) left join nodes n on n.id = r.id where n.id is null` should return 0.

- **`20250007` conflict.** If the migration has been partially applied
  (unlikely given the "not yet applied" note in archive/phase-4-plan.md, but
  check), migration 20250011 will fail on `drop column assignment_id` since
  the column may not exist or the constraint name may differ. Verify
  `\d public.attempts` before running step 4.

- **`/add-interest` dedup hallucination.** Haiku may return a `matched_node_slug`
  not in the shortlist. The route must validate the slug exists in the candidate
  set before using it, falling back to `'new'` verdict. Test with a deliberately
  small candidate set.

- **Survey form UX on mobile.** Node-rating grid (21 nodes × 3 states) is the
  hardest UI piece in the phase. Test on a real phone before sign-off.

- **Cold first-run latency for `/add-interest`.** Haiku + Sonnet in sequence
  for a genuinely new node can take 15–25s for a user with a complex free-text
  intent that generates 3 new interest nodes. Show a "building your graph…"
  loading state on the survey submit.

## Things easy to forget

- **`20250007` must NOT be applied.** It's superseded by 20250011.
- **Dedup is autonomous.** No user confirmation step — system decides,
  operator reviews weekly.
- **`nodes.slug` unique constraint** prevents dupe nodes at the DB level;
  race collisions flow to `curation_proposals`.
- **`mode_balance 0.0 = all problems, 1.0 = all papers.**
- **Every Claude call logged to `llm_calls`** — including the two `/add-interest`
  calls. Both use the existing `call_json` helper which logs automatically.
- **Sonnet 4.6 = `claude-sonnet-4-6`. Haiku = `claude-haiku-4-5-20251001`.**
- **Next.js 16.** Auth proxy at `web/proxy.ts`, exported function `proxy`.
  Tailwind v4: `@import "tailwindcss"`. `web/` has its own `.git`.
- **Every RLS-enabled table needs a SELECT policy** for server-client reads,
  not just INSERT/UPDATE. Writes via the admin/service-role client bypass RLS
  entirely, so a missing SELECT policy only shows up as a silent null return
  when reading from the auth-scoped server client — it looks like the row was
  never written. Check both write *and* read policies when adding a new table.
- **`postgrest-py upsert(ignore_duplicates=True)` does NOT suppress 23505.**
  The flag sets a PostgREST `Prefer` header that often doesn't propagate as
  expected. Use `try/except` with a `_is_unique_violation(exc)` check instead.
  The route already has that helper for the node insert — apply the same pattern
  to any other table where duplicate-on-conflict is acceptable.

## Handoff to Phase 5-rev (preview)

Phase 5-rev picks up with:
- The new graph and queue fully in place.
- A user who has completed the survey and sees their daily-three (mocked).
- `attempts` table in its v2 shape (no `assignment_id`, has `queue_item_id`).

Phase 5-rev adds:
- `POST /parse-solution` (the unfinished v1 Phase 4 vision-parsing work).
- `POST /grade-solution` (dialogic feedback, writes `grade_response_md`).
- Refactor of `/generate-problem` to read from `nodes` and tie to `queue_item_id`.
- Real problem flow: upload → parse → review → submit → grade → notebook entry.
- Skill tree view (React Flow + Dagre against `nodes`/`edges`/`user_node_states`).
- Notebook browse + read.

---

## Deviations (steps 12–13)

### Step 12 — type cleanup went further than specified

`web/lib/types.ts` also had stale field names on the surviving `Problem` interface
(`canonical_topic_id`, `generated_context_md`) which were renamed in migration
`20250011`. These were corrected to `topic_node_id` and `context_md` in the same
pass. The full set of v2 types added: `Edge`, `QueueItem` (with `QueueItemKind`
and `QueueItemState` aliases), `SurfacedPick`, `UserNodeState`, `UserInterest`.

### Step 13 — placeholder queue seeding added to survey route

The acceptance test criteria required cards to render on `/daily`, but `update_queue`
is a no-op stub so no `queue_items` are written. To unblock the layout test without
implementing the real queue-build logic, the survey route (`web/app/api/survey/route.ts`)
was extended to seed one `suggested_interest` queue item per `user_interests` row after
all `addInterest` calls complete. This gives the daily page cards to render with.

**Phase 7-rev must handle this:** when real `update_queue` lands, it needs to avoid
double-seeding items for interests that already have a `suggested_interest` queue item.
There is currently no unique constraint on `(user_id, kind, ref_id)` in `queue_items`,
so re-submitting the survey creates duplicate items.

### Step 13 — dedup bug found and fixed during acceptance

Sending a multi-topic free-text string (e.g. "I want to learn quantum mech, solid state
physics, and Kalman filters") as a single `/add-interest` call caused near-duplicate node
generation across repeated survey submissions. Root cause: Haiku's single-verdict dedup
was returning `"related"` for known topics in a multi-topic sentence rather than `"same"`,
and Sonnet was generating duplicate-titled nodes because only slug uniqueness was
constrained, not title uniqueness.

Three fixes applied:

1. **Dedup prompt tightened** (`api/prompts/add_interest.py`): `"same"` is now preferred
   when the expression covers the same subject area, even with minor phrasing differences.
   `"related"` requires meaningfully different scope/domain/level. `"new"` is a last resort.

2. **Title collision detection** (`api/routes/add_interest.py`): after Sonnet generates a
   node, if its title (case-insensitive) matches any existing node, the route links the
   user to the existing node and writes a `curation_proposals` merge row rather than
   inserting a duplicate. New test: `test_title_collision_links_to_existing_no_new_insert`.

3. **Existing titles passed to generate prompt**: Sonnet is now told the list of existing
   titles alongside existing slugs and instructed not to duplicate either.

**Structural limitation still present:** sending a multi-topic sentence as one
`addInterest` call can only ever produce one node — the most "novel" aspect of the text
gets a node; the others are handled by Haiku's dedup returning `"same"` if they match
existing nodes. The longer-term fix (Phase 7-rev or later) is an upstream extraction
step that parses free text into discrete topic expressions before fanning out to
per-topic `addInterest` calls.

---

## Session handoff — Phase 4-rev complete

*Written for a fresh Claude session starting Phase 5-rev.*

### Database state (all migrations applied)

| Migration | What it did |
|---|---|
| `20250008_graph_schema.sql` | Created `nodes`, `edges`, `user_node_states`, `user_interests`, `bookmarks`, `curation_proposals`, `megagraph_snapshots`. Added `profiles.timezone`. |
| `20250009_queue_schema.sql` | Created `queue_items`, `surfaced_picks`, `refresher_schedule`. |
| `20250010_papers_schema.sql` | Created `papers`, `paper_engagements`, `paper_answers`, `paper_qa`, `notebook_entries` (with FTS on title). |
| `20250011_modify_problems_attempts_surveys.sql` | Renamed `problems.canonical_topic_id → topic_node_id`, `generated_context_md → context_md`. Added versioning, tags, paper_id, pool_status, time estimates. Dropped `attempts.assignment_id`; added `queue_item_id`, grade flags, `grade_response_md`, `disputed`. Restructured `surveys` for v2 shape. |
| `20250012_seed_nodes_edges.sql` | Copied 13 foundation + 8 interest nodes from `canonical_topics` into `nodes` (UUID-preserving). Copied 28 edges. Added FK `problems.topic_node_id → nodes(id)`. DEPRECATED v1 tables. |
| `20250013_surveys_rls.sql` | Added SELECT RLS policy on `surveys`. |

Migration `20250007_phase4_attempts.sql` was **never applied** and must stay unapplied.

### Code state

All v1 plan-flow code has been deleted. The full v2 flow is working end-to-end:
sign up → survey (free-text intent + node ratings + mode balance) → interests added to
megagraph (Haiku dedup + Sonnet generate) → `/daily` shows surfaced queue items.

The `/daily` page currently shows `suggested_interest` placeholder items seeded during the
survey. Real problem and paper items appear once Phase 5-rev wires `/generate-problem` to
write `queue_items`.

### Key files for Phase 5-rev

**FastAPI (`api/`):**
- `routes/add_interest.py` — Haiku dedup + Sonnet generate + title-collision detection + user_interests write. 8 tests in `tests/test_add_interest.py`.
- `routes/surface_daily.py` — deterministic kind-varied picking, writes `surfaced_picks`. 9 tests in `tests/test_surface_daily.py`.
- `routes/update_queue.py` — **no-op stub**; replace in Phase 7-rev.
- `routes/generate_problem.py` — still reads from `canonical_topics` and uses `plan_node_id`. **Must be refactored in Phase 5-rev step 3** to read from `nodes` and accept a `queue_item_id`.

**Next.js (`web/`):**
- `app/api/survey/route.ts` — seeds placeholder `queue_items` after interests are added. Phase 7-rev must avoid re-seeding duplicates.
- `lib/queueHelpers.ts` — `getOrSurfacePick`: checks for an open `surfaced_picks` row, loads its items, or calls `/surface-daily`. Called directly from the `/daily` server component (not via the API route — avoids a self-referential HTTP call).
- `lib/pythonApi.ts` — `generateProblem` wrapper still passes stale `plan_node_id`. **Update in Phase 5-rev step 3** when the route is refactored.
- `lib/types.ts` — v1 types removed; v2 types present: `Node`, `Edge`, `QueueItem`, `SurfacedPick`, `UserNodeState`, `UserInterest`, `SurveyV2Payload`, `QueueResult`. `Problem` interface uses current field names (`topic_node_id`, `context_md`).

### Things to watch in Phase 5-rev

- **`generate_problem.py` refactor**: inputs change from `plan_node_id` to `queue_item_id` + `node_id`. The difficulty curve (previously from `surveys.difficulty_curve`, now dropped) should derive from `user_node_states.struggle_score` for the relevant node.
- **Problem cache key**: the two partial unique indexes (`problems_cache_key_with_hook`, `problems_cache_key_no_hook`) already use `topic_node_id` — they are correct and should be respected by the refactored route.
- **`attempts.queue_item_id` FK has no cascade** — deleting a queue item orphans the attempt. This is intentional (attempts are permanent records); just be aware when writing tests that delete queue items.
- **`add_interest` dedup: use `try/except` + `_is_unique_violation()`**, never `upsert(ignore_duplicates=True)`. See `feedback_postgrest_upsert_ignore_duplicates.md` in memory.
- **`queue_items` placeholder items from survey**: when Phase 5-rev's problem generation writes real `problem` queue items, the existing `suggested_interest` placeholders remain in the queue. The daily page will show a mix until Phase 7-rev's `update_queue` prunes them.

### Test data reset SQL

When re-running acceptance tests, use this to return to a clean post-migration state
(preserves profiles and seeded nodes):

```sql
begin;
delete from public.surfaced_picks;
delete from public.attempts;
delete from public.queue_items;
delete from public.refresher_schedule;
delete from public.paper_answers;
delete from public.paper_qa;
delete from public.paper_engagements;
delete from public.notebook_entries;
delete from public.bookmarks;
delete from public.surveys;
delete from public.user_node_states;
delete from public.user_interests;
delete from public.nodes where created_by_user_id is not null;
delete from public.curation_proposals;
delete from public.megagraph_snapshots;
delete from public.llm_calls;
commit;
```
