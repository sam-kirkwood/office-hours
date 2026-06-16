-- Phase 12 Step 4a — fb1: feedback / report-a-problem channel.
--
-- Always-available catch-all for user reports. The curiosity-box router
-- (Step 4c) will redirect feedback-flavoured input here. Operator reads
-- via service_role (bypasses RLS); users can only INSERT their own rows.

create table public.feedback_reports (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references public.profiles(id) on delete cascade,
  url          text not null,
  category     text not null check (category in (
                 'bug', 'confusing_copy', 'bad_problem_or_paper', 'other'
               )),
  body         text not null,
  created_at   timestamptz not null default now(),
  resolved_at  timestamptz
);

alter table public.feedback_reports enable row level security;

create policy "users insert own feedback"
  on public.feedback_reports for insert
  to authenticated
  with check (user_id = auth.uid());
