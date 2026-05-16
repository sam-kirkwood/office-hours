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

create index nodes_kind_idx        on public.nodes (kind);
create index nodes_domain_idx      on public.nodes (domain);
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
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles(id) on delete cascade,
  node_id    uuid not null references public.nodes(id) on delete cascade,
  weight     real not null default 1.0,
  added_via  text not null check (added_via in ('survey','explicit_request','cross_pollination')),
  created_at timestamptz not null default now(),
  unique (user_id, node_id)
);

create index user_interests_user_idx on public.user_interests (user_id);

-- bookmarks
create table public.bookmarks (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.profiles(id) on delete cascade,
  kind           text not null check (kind in ('node','paper','problem','concept')),
  ref_id_or_text text not null,
  created_at     timestamptz not null default now(),
  promoted_at    timestamptz
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
alter table public.nodes              enable row level security;
alter table public.edges              enable row level security;
alter table public.user_node_states   enable row level security;
alter table public.user_interests     enable row level security;
alter table public.bookmarks          enable row level security;
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
