-- Phase 1 schema: minimal stubs for skeleton build.
-- All tables use UUID PKs and timestamptz. Columns will be expanded in later phases.

-- profiles: extends auth.users (Supabase convention; ARCHITECTURE.md calls this 'users')
create table public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  email        text not null,
  display_name text,
  created_at   timestamptz not null default now()
);

-- surveys stub: Phase 2 will add background_json, skill_ratings_json, etc.
create table public.surveys (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- problems stub: Phase 3 will add difficulty, context_hook_id, generated_by_llm_call_id, etc.
create table public.problems (
  id           uuid primary key default gen_random_uuid(),
  statement_md text not null,
  solution_md  text,
  created_at   timestamptz not null default now()
);

-- daily_assignments stub
create table public.daily_assignments (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references public.profiles(id) on delete cascade,
  problem_id        uuid not null references public.problems(id),
  assigned_for_date date not null,
  status            text not null default 'pending'
    check (status in ('pending', 'in_progress', 'submitted', 'graded')),
  unique (user_id, assigned_for_date)
);

-- attempts stub: Phase 4 will add parsed_markdown, user_edited_markdown, hint_levels_used, etc.
create table public.attempts (
  id               uuid primary key default gen_random_uuid(),
  assignment_id    uuid not null references public.daily_assignments(id) on delete cascade,
  user_id          uuid not null references public.profiles(id) on delete cascade,
  problem_id       uuid not null references public.problems(id),
  raw_image_paths  text[] not null default '{}',
  submitted_at     timestamptz,
  created_at       timestamptz not null default now()
);

-- auto-create a profile row whenever a new user signs up via Supabase Auth
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Row Level Security
alter table public.profiles          enable row level security;
alter table public.surveys           enable row level security;
alter table public.problems          enable row level security;
alter table public.daily_assignments enable row level security;
alter table public.attempts          enable row level security;

-- profiles: each user manages their own row
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id);

-- problems: any authenticated user can read
create policy "problems_select_authenticated" on public.problems
  for select using (auth.role() = 'authenticated');

-- daily_assignments: users see only their own
create policy "assignments_select_own" on public.daily_assignments
  for select using (auth.uid() = user_id);

-- attempts: users read and write their own rows
create policy "attempts_select_own" on public.attempts
  for select using (auth.uid() = user_id);
create policy "attempts_insert_own" on public.attempts
  for insert with check (auth.uid() = user_id);
create policy "attempts_update_own" on public.attempts
  for update using (auth.uid() = user_id);
