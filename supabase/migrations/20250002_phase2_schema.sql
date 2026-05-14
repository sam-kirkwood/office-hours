-- Phase 2: curriculum graph, user plans, and survey expansion.

-- Expand surveys stub with real columns
alter table public.surveys
  add column background_json       jsonb,
  add column skill_ratings_json    jsonb,
  add column desired_topics_json   jsonb,
  add column difficulty_curve      text check (difficulty_curve in ('gentle', 'standard', 'aggressive'));

-- One survey per user (allow upsert in Phase 2)
alter table public.surveys
  add constraint surveys_user_id_unique unique (user_id);

-- Canonical curriculum graph
create table public.canonical_topics (
  id              uuid primary key default gen_random_uuid(),
  slug            text not null unique,
  title           text not null,
  description     text,
  difficulty_band text not null check (difficulty_band in ('intro', 'core', 'advanced')),
  domain          text not null,
  created_at      timestamptz not null default now()
);

create table public.canonical_edges (
  id                    uuid primary key default gen_random_uuid(),
  prerequisite_topic_id uuid not null references public.canonical_topics(id) on delete cascade,
  dependent_topic_id    uuid not null references public.canonical_topics(id) on delete cascade,
  weight                integer not null default 1,
  unique (prerequisite_topic_id, dependent_topic_id)
);

-- Operator review queue for topics users requested that aren't in the graph
create table public.pending_topic_requests (
  id                   uuid primary key default gen_random_uuid(),
  requested_by_user_id uuid not null references public.profiles(id) on delete cascade,
  raw_topic_text       text not null,
  proposed_node_json   jsonb,
  status               text not null default 'pending'
    check (status in ('pending', 'approved', 'rejected')),
  created_at           timestamptz not null default now()
);

-- User learning plans
create table public.user_plans (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles(id) on delete cascade,
  status           text not null default 'pending_review'
    check (status in ('pending_review', 'active', 'completed')),
  adjustment_notes text,
  created_at       timestamptz not null default now()
);

create table public.plan_nodes (
  id                       uuid primary key default gen_random_uuid(),
  plan_id                  uuid not null references public.user_plans(id) on delete cascade,
  canonical_topic_id       uuid not null references public.canonical_topics(id),
  order_index              integer not null,
  state                    text not null default 'pending'
    check (state in ('pending', 'active', 'struggling', 'mastered')),
  problems_completed_count integer not null default 0
);

-- Row Level Security
alter table public.canonical_topics         enable row level security;
alter table public.canonical_edges          enable row level security;
alter table public.pending_topic_requests   enable row level security;
alter table public.user_plans               enable row level security;
alter table public.plan_nodes               enable row level security;

-- canonical_topics + edges: any authenticated user can read
create policy "canonical_topics_select" on public.canonical_topics
  for select using (auth.role() = 'authenticated');

create policy "canonical_edges_select" on public.canonical_edges
  for select using (auth.role() = 'authenticated');

-- pending_topic_requests: users manage their own
create policy "ptr_select_own" on public.pending_topic_requests
  for select using (auth.uid() = requested_by_user_id);
create policy "ptr_insert_own" on public.pending_topic_requests
  for insert with check (auth.uid() = requested_by_user_id);

-- user_plans: users read/update their own; inserts go through service role (API route)
create policy "user_plans_select_own" on public.user_plans
  for select using (auth.uid() = user_id);
create policy "user_plans_update_own" on public.user_plans
  for update using (auth.uid() = user_id);

-- plan_nodes: users read their own; writes go through service role
create policy "plan_nodes_select_own" on public.plan_nodes
  for select using (
    exists (
      select 1 from public.user_plans up
      where up.id = plan_nodes.plan_id and up.user_id = auth.uid()
    )
  );
