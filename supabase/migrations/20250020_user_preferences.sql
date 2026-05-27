-- Phase 10-rev Step 2e — user_preferences table.
--
-- Stores high-level feedback toggles set from the profile page (survey-and-
-- difficulty-design.md §6). Each row is one (user, key) pair; presence of a
-- row means the toggle is active. The value is free-form text so future
-- preferences can store strings or stringified numbers without a migration.
--
-- Initial keys (Step 2e):
--   feedback_too_hard, feedback_assume_less,
--   feedback_more_papers, feedback_harder_problems
--
-- Read by the problem generator (Step 2f) as soft biases on the dials.

create table public.user_preferences (
  user_id     uuid not null references public.profiles(id) on delete cascade,
  key         text not null,
  value       text not null,
  updated_at  timestamptz not null default now(),
  primary key (user_id, key)
);

alter table public.user_preferences enable row level security;

create policy user_preferences_own_select on public.user_preferences
  for select using (auth.uid() = user_id);

create policy user_preferences_own_modify on public.user_preferences
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
