-- Phase 3 schema: AI-generated problems, pre-stored hints, curated context
-- hooks, and an llm_calls audit log for cost observability.

-- ----------------------------------------------------------------------------
-- llm_calls: every Anthropic API call gets a row. Created before the tables
-- that reference it so foreign keys resolve.
-- ----------------------------------------------------------------------------
create table public.llm_calls (
  id                  uuid primary key default gen_random_uuid(),
  route               text not null,
  model               text not null,
  input_tokens        integer not null default 0,
  output_tokens       integer not null default 0,
  cache_read_tokens   integer not null default 0,
  cache_write_tokens  integer not null default 0,
  estimated_cost_usd  numeric(10, 6) not null default 0,
  request_summary     jsonb,
  response_summary    jsonb,
  user_id             uuid references public.profiles(id) on delete set null,
  created_at          timestamptz not null default now()
);

create index llm_calls_created_at_idx on public.llm_calls (created_at desc);
create index llm_calls_user_id_idx    on public.llm_calls (user_id);

-- ----------------------------------------------------------------------------
-- context_hooks: curated historical/scientific episodes attached to topics.
-- ----------------------------------------------------------------------------
create table public.context_hooks (
  id                uuid primary key default gen_random_uuid(),
  slug              text not null unique,
  title             text not null,
  summary_md        text not null,
  related_topic_ids uuid[] not null default '{}',
  difficulty_band   text not null check (difficulty_band in ('intro', 'core', 'advanced')),
  sources_json      jsonb not null default '[]'::jsonb,
  created_by        uuid references public.profiles(id) on delete set null,
  created_at        timestamptz not null default now()
);

create index context_hooks_related_topic_ids_idx on public.context_hooks using gin (related_topic_ids);
create index context_hooks_difficulty_band_idx   on public.context_hooks (difficulty_band);

-- ----------------------------------------------------------------------------
-- Expand the problems stub with the columns Phase 3 actually needs. The new
-- columns are nullable so any Phase 1 stub rows survive the migration; new
-- rows from the Python service will always populate canonical_topic_id and
-- difficulty.
-- ----------------------------------------------------------------------------
alter table public.problems
  add column canonical_topic_id       uuid references public.canonical_topics(id),
  add column rubric_md                text,
  add column difficulty               smallint check (difficulty between 1 and 5),
  add column context_hook_id          uuid references public.context_hooks(id),
  add column generated_by_llm_call_id uuid references public.llm_calls(id);

-- Cache key: one problem per (canonical_topic_id, difficulty, context_hook_id)
-- is reused across users. Two partial unique indexes cover the hook-present
-- and hook-absent cases; together they make the on-conflict-do-nothing insert
-- race-safe.
create unique index problems_cache_key_with_hook on public.problems
  (canonical_topic_id, difficulty, context_hook_id)
  where context_hook_id is not null;

create unique index problems_cache_key_no_hook on public.problems
  (canonical_topic_id, difficulty)
  where canonical_topic_id is not null and context_hook_id is null;

-- ----------------------------------------------------------------------------
-- problem_hints: levels 1..5, pre-generated at problem-creation time and
-- never regenerated per request.
-- ----------------------------------------------------------------------------
create table public.problem_hints (
  id          uuid primary key default gen_random_uuid(),
  problem_id  uuid not null references public.problems(id) on delete cascade,
  level       smallint not null check (level between 1 and 5),
  text        text not null,
  created_at  timestamptz not null default now(),
  unique (problem_id, level)
);

create index problem_hints_problem_id_idx on public.problem_hints (problem_id);

-- ----------------------------------------------------------------------------
-- daily_assignments: track which plan node this assignment advanced so plan
-- adaptation in Phase 5 has the link without joining through problems.
-- ----------------------------------------------------------------------------
alter table public.daily_assignments
  add column plan_node_id uuid references public.plan_nodes(id) on delete set null;

-- ----------------------------------------------------------------------------
-- Tighten the problems SELECT policy now that problems contain solutions and
-- rubrics. Users can only read a problem they have a daily_assignment for.
-- Service role (Python service, server-side Next.js helpers) bypasses RLS.
-- ----------------------------------------------------------------------------
drop policy "problems_select_authenticated" on public.problems;
create policy "problems_select_via_assignment" on public.problems
  for select using (
    exists (
      select 1 from public.daily_assignments da
      where da.problem_id = problems.id and da.user_id = auth.uid()
    )
  );

-- ----------------------------------------------------------------------------
-- Row Level Security on the new tables.
-- ----------------------------------------------------------------------------
alter table public.context_hooks enable row level security;
alter table public.problem_hints enable row level security;
alter table public.llm_calls     enable row level security;

-- context_hooks: readable by any authenticated user (they show up in the
-- context section of the daily-problem page).
create policy "context_hooks_select" on public.context_hooks
  for select using (auth.role() = 'authenticated');

-- problem_hints: readable only when the user has an assignment for the
-- problem. Mirrors the problems policy.
create policy "problem_hints_select_via_assignment" on public.problem_hints
  for select using (
    exists (
      select 1 from public.daily_assignments da
      where da.problem_id = problem_hints.problem_id
        and da.user_id = auth.uid()
    )
  );

-- llm_calls has no policies — only service role reads or writes (admin cost
-- dashboard in Phase 6 will use the service role).
