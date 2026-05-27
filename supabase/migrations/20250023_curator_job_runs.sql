-- Phase 10-rev Step 3d — curator_job_runs job log.
--
-- /run-daily-planner writes one row per invocation. The pg_cron daily job
-- (migration 20250024) is the main writer; cold-start (Stage 7 survey
-- completion) and manual operator runs also land here.
--
-- This table is operator-only — Sam reads it via the admin SQL editor /
-- future cost dashboard. RLS is enabled with no end-user policy, so service
-- role is the only path that can read or write.

create table public.curator_job_runs (
  id                             uuid primary key default gen_random_uuid(),
  user_id                        uuid not null references public.profiles(id) on delete cascade,
  triggered_by                   text not null check (triggered_by in ('cron','cold_start','manual')),
  plan_queue_status              text check (plan_queue_status in ('ok','error','skipped')),
  plan_queue_items_added         int default 0,
  plan_queue_items_reprioritised int default 0,
  plan_queue_items_skipped       int default 0,
  check_deferred_requeued        int default 0,
  check_deferred_kept            int default 0,
  error_message                  text,
  started_at                     timestamptz not null default now(),
  finished_at                    timestamptz
);

create index curator_job_runs_user_started_idx
  on public.curator_job_runs (user_id, started_at desc);

create index curator_job_runs_started_idx
  on public.curator_job_runs (started_at desc);

alter table public.curator_job_runs enable row level security;
-- No end-user RLS policy: service role only.
