-- Add generated_context_md to problems. Populated by Sonnet when no curated
-- context_hook matched the topic (Sonnet writes a 2–4 paragraph historical /
-- scientific context block inline). Always null when context_hook_id is set —
-- the daily page picks one or the other for the context section.
--
-- Bug-fix follow-up to phase-3 step 4: the column was specified in the
-- `GeneratedProblem` pydantic schema but never added to the DB, so the field
-- was silently dropped on insert.

alter table public.problems
  add column generated_context_md text;
