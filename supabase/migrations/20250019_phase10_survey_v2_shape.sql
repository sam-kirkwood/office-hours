-- Phase 10-rev Step 2c — additive columns to drive the seven-stage onboarding
-- survey (survey-and-difficulty-design.md §1).
--
-- Each onboarding stage is its own route under /survey/<stage>; the surveys
-- row IS the working draft. These columns let stages persist their output
-- progressively so the user can reload mid-survey without losing state, and
-- so the route-per-stage shell can gate the user back to the earliest
-- incomplete stage.
--
-- background_json    — Stage 1 selections (domain chips + relationship cards).
--                       Free-text intent reuses the existing free_text_intent
--                       column (its semantics shift from "interest expression"
--                       to "background blurb" per §1.2.3).
-- completed_stages   — Ordered list of stages the user has finished. Cheap
--                       gate for the route-per-stage shell; the survey shell
--                       reads this on every page load.
-- pending_interests  — Stage 3 selections (tile slugs + free text) handed
-- _json                off to the Stage 4+5 stub at server time. Empty after
--                       the stub runs. The full Stage 4 add-interest dialog
--                       lands in Step 2d and will read this same column.

alter table public.surveys
  add column background_json jsonb not null default '{}'::jsonb,
  add column completed_stages text[] not null default '{}'::text[],
  add column pending_interests_json jsonb not null default '{}'::jsonb;
