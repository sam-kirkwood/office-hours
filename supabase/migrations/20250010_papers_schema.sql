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
  id                 uuid primary key default gen_random_uuid(),
  engagement_id      uuid not null references public.paper_engagements(id) on delete cascade,
  question_id        uuid not null,   -- references questions_json[].id
  user_response_md   text,
  claude_response_md text,
  submitted_at       timestamptz
);

create table public.paper_qa (
  id                 uuid primary key default gen_random_uuid(),
  engagement_id      uuid not null references public.paper_engagements(id) on delete cascade,
  turn_index         smallint not null,
  user_message_md    text not null,
  claude_response_md text,
  created_at         timestamptz not null default now()
);

create table public.notebook_entries (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.profiles(id) on delete cascade,
  entry_kind       text not null check (entry_kind in ('problem_attempt','paper_engagement')),
  ref_id           uuid not null,
  title            text not null,
  topic_node_slugs text[] not null default '{}',
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  fts_vector       tsvector generated always as (
                     to_tsvector('english'::regconfig, coalesce(title,''))
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
