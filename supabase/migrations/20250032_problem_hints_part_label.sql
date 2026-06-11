-- Phase 10.5-rev Step 3 (d10) — problem_hints.part_label.
--
-- Multi-part problems carry a single five-rung *depth* hint ladder
-- (L1 name-concept … L5 pitfall) that applies to the whole problem. A user
-- opening "Hint 4" can't tell which part it speaks to, and so fears revealing
-- a part they hadn't asked for help on.
--
-- part_label is a short, human-facing tag naming the part(s) a hint addresses
-- ("Parts (a)–(b)", "Part (c)", or "Whole problem"). It is nullable: existing
-- hints have none until the Haiku reformat backfill (scripts/reformat_problems.py)
-- assigns them, and the render layer simply omits the chip when null, so the
-- column is additive and tolerant of every existing row.

alter table public.problem_hints
  add column part_label text;
