-- Phase 4 schema: extend the `attempts` stub with the columns the vision
-- parsing + review flow actually writes.
--
-- See dev-docs/phase-4-plan.md §"Step 1" for the rationale. The new columns
-- are nullable (or have a sensible default) so any Phase 1 stub rows survive
-- the migration — in practice the table is empty because the upload page has
-- been a mocked stub since Phase 1, but the migration is written to be safe
-- against that assumption being wrong.

-- ----------------------------------------------------------------------------
-- New columns on attempts.
--
-- parse_status is an explicit enum rather than null-vs-set semantics because
-- 'parse_failed' is a real terminal state the UI must distinguish from
-- 'not yet parsed'. Lifecycle:
--   pending      -- row just inserted; parse route not yet invoked
--   parsing      -- parse route running; vision call in flight
--   parsed       -- parse route succeeded; parsed_markdown populated
--   parse_failed -- parse route exhausted retries; parsed_markdown is "" and
--                   the UI shows the scaffolded textarea fallback
--   confirmed    -- user reviewed/edited and clicked submit; user_edited_markdown
--                   and submitted_at are set; daily_assignments.status='submitted'
--
-- parsed_by_llm_call_id mirrors problems.generated_by_llm_call_id so the
-- Phase 6 cost dashboard can attribute spend back to the attempt.
-- ----------------------------------------------------------------------------
alter table public.attempts
  add column parsed_markdown        text,
  add column user_edited_markdown   text,
  add column hint_levels_used       smallint[] not null default '{}',
  add column parse_status           text not null default 'pending'
    check (parse_status in ('pending', 'parsing', 'parsed', 'parse_failed', 'confirmed')),
  add column parsed_by_llm_call_id  uuid references public.llm_calls(id);

-- ----------------------------------------------------------------------------
-- One attempt per assignment for v1. The one-problem-per-day gate on
-- daily_assignments (unique (user_id, assigned_for_date) from migration
-- 20250001) is the upstream invariant; this constraint enforces the same shape
-- one layer down so the upload-page state machine can rely on at-most-one
-- attempt row.
--
-- When bonus problems land post-v1 (see phase-3-plan.md follow-up #5), the
-- plan is to introduce a separate bonus_assignments table rather than relax
-- this constraint, so "today's canonical attempt" stays unambiguous.
-- ----------------------------------------------------------------------------
alter table public.attempts
  add constraint attempts_one_per_assignment unique (assignment_id);

-- ----------------------------------------------------------------------------
-- RLS: no policy changes needed.
--
-- attempts_select_own / attempts_insert_own / attempts_update_own from
-- migration 20250001 already gate on auth.uid() = user_id; new columns
-- inherit the same row-level checks. The service-role client used by the
-- Next.js API routes and the Python service bypasses RLS as usual.
-- ----------------------------------------------------------------------------
