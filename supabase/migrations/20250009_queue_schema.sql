create table public.queue_items (
  id                         uuid primary key default gen_random_uuid(),
  user_id                    uuid not null references public.profiles(id) on delete cascade,
  kind                       text not null
                               check (kind in ('problem','paper_engagement','refresher',
                                               'concept_review','suggested_interest')),
  ref_id                     uuid,
  state                      text not null default 'pending'
                               check (state in ('pending','surfaced','in_progress',
                                                'done','skipped','dismissed')),
  priority_score             real not null default 0.0,
  time_estimate_minutes_low  smallint,
  time_estimate_minutes_high smallint,
  added_reason               text,
  added_at                   timestamptz not null default now(),
  updated_at                 timestamptz not null default now()
);

create index queue_items_user_state_idx    on public.queue_items (user_id, state);
create index queue_items_user_priority_idx on public.queue_items (user_id, priority_score desc);

create table public.surfaced_picks (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.profiles(id) on delete cascade,
  queue_item_ids uuid[] not null,   -- length 1–3; see pivot-plan §F8
  surfaced_at    timestamptz not null default now(),
  replaced_at    timestamptz,
  chosen_item_id uuid references public.queue_items(id) on delete set null
);

create index surfaced_picks_user_idx on public.surfaced_picks (user_id);

create table public.refresher_schedule (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references public.profiles(id) on delete cascade,
  subject_kind   text not null check (subject_kind in ('attempt','engagement','concept')),
  subject_ref_id uuid not null,
  due_at         timestamptz not null,
  surfaced_at    timestamptz
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
