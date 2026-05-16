-- ── problems ─────────────────────────────────────────────────────────────────

-- Rename canonical_topic_id → topic_node_id. FK to nodes(id) is added in
-- step 5 once nodes rows exist.
alter table public.problems
  rename column canonical_topic_id to topic_node_id;

-- Rename generated_context_md → context_md (same column, cleaner name)
alter table public.problems
  rename column generated_context_md to context_md;

alter table public.problems
  add column version                    smallint not null default 1,
  add column previous_version_id        uuid references public.problems(id),
  add column tags                       text[] not null default '{}',
  add column paper_id                   uuid references public.papers(id),
  add column pool_status                text not null default 'active'
                                          check (pool_status in ('active','retired','flagged')),
  add column time_estimate_minutes_low  smallint,
  add column time_estimate_minutes_high smallint;

-- Rewrite cache-key partial indexes to use topic_node_id and exclude paper-tied
-- problems (paper-tied problems are not pool-reusable per CLAUDE.md).
drop index if exists problems_cache_key_with_hook;
drop index if exists problems_cache_key_no_hook;

create unique index problems_cache_key_with_hook on public.problems
  (topic_node_id, difficulty, context_hook_id)
  where context_hook_id is not null and paper_id is null;

create unique index problems_cache_key_no_hook on public.problems
  (topic_node_id, difficulty)
  where topic_node_id is not null and context_hook_id is null and paper_id is null;

-- ── attempts ──────────────────────────────────────────────────────────────────

-- Drop the v1 assignment coupling. No live data — safe to drop outright.
-- The unique constraint is from 20250007 (never applied) so IF EXISTS is a no-op.
alter table public.attempts
  drop constraint if exists attempts_one_per_assignment;

alter table public.attempts
  drop column assignment_id;

alter table public.attempts
  add column queue_item_id     uuid references public.queue_items(id),
  add column marked_refreshed  boolean not null default false,
  add column requested_easier  boolean not null default false,
  add column requested_harder  boolean not null default false,
  add column parent_attempt_id uuid references public.attempts(id),
  add column grade_response_md text,
  add column disputed          boolean not null default false;

-- ── surveys ───────────────────────────────────────────────────────────────────

alter table public.surveys
  drop column if exists background_json,
  drop column if exists topic_states_json,
  drop column if exists difficulty_curve;

alter table public.surveys
  add column free_text_intent       text,
  add column node_ratings_json      jsonb not null default '{}',
  add column comfort_responses_json jsonb not null default '{}',
  add column mode_balance           real not null default 0.0
                                      check (mode_balance between 0.0 and 1.0),
  add column updated_at             timestamptz not null default now();
