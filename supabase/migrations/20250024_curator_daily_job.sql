-- Phase 10-rev Step 3d — daily curator background job (pg_cron + pg_net).
--
-- ============================================================================
-- OPERATOR PREREQUISITES — apply these in the Supabase dashboard BEFORE
-- running `npx supabase db push` on this migration:
--
--   1. Database → Extensions:
--        Enable `pg_cron` and `pg_net` (both ship with Supabase but require
--        explicit enablement).
--
--   2. Database → Vault → Secrets:
--        Create a secret named `internal_api_token` whose value matches the
--        Python service's `INTERNAL_API_TOKEN` (also stored in `api/.env`
--        and the FastAPI host's env vars).
--
--   3. Database → Settings → Postgres Config (or via SQL):
--        ALTER DATABASE postgres SET app.python_api_url =
--          'https://<your-fastapi-host>';   -- e.g. https://office-hours-api.fly.dev
--        Reload settings via `SELECT pg_reload_conf();` or the dashboard.
--
-- Without these, the cron job will run but produce HTTP errors. The
-- `curator_job_runs` table will stay empty (the failures happen before the
-- FastAPI side ever sees the request).
--
-- Verification after push:
--   SELECT * FROM cron.job WHERE jobname = 'curator_daily';
-- Manual trigger:
--   SELECT cron.run_job(jobid) FROM cron.job WHERE jobname = 'curator_daily';
-- ============================================================================

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Idempotent: drop any prior schedule with this name before re-creating.
do $$
begin
  if exists (select 1 from cron.job where jobname = 'curator_daily') then
    perform cron.unschedule('curator_daily');
  end if;
end$$;

-- Daily at 07:00 UTC. Selects users who have engaged in the past 14 days
-- (an "active user" per curriculum-curator-design.md §13.2) and fires one
-- HTTP POST to /run-daily-planner per user. pg_net returns immediately with
-- a request id; the FastAPI service handles each call independently.
--
-- pg_net timeout = 60s/call: covers the worst case where /plan-queue's
-- pool-miss path triggers an inline /generate-problem (Sonnet generation).
select cron.schedule(
  'curator_daily',
  '0 7 * * *',
  $cron$
  with active_users as (
    select distinct user_id from (
      select user_id from public.attempts
        where submitted_at > now() - interval '14 days' and submitted_at is not null
      union all
      select pe.user_id
        from public.paper_answers pa
        join public.paper_engagements pe on pe.id = pa.engagement_id
        where pa.submitted_at > now() - interval '14 days' and pa.submitted_at is not null
    ) u
  )
  select net.http_post(
    url := current_setting('app.python_api_url') || '/run-daily-planner',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'internal_api_token'
      )
    ),
    body := jsonb_build_object(
      'user_id', user_id,
      'triggered_by', 'cron'
    ),
    timeout_milliseconds := 60000
  )
  from active_users;
  $cron$
);
