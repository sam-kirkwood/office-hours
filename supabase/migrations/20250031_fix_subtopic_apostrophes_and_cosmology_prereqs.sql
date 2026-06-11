-- Phase 10.5-rev Step 4 — megagraph data repairs (t2).
--
-- Two independent corrections to seeded megagraph data, both surfaced by the
-- operator walkthrough when adding "Cosmology & the Lambda-CDM Model" and
-- seeing its concept tour (survey-and-difficulty-design.md §1.6):
--
--   1. Doubled apostrophes ('') in foundation-node subtopic titles.
--   2. Wrong prerequisite edges on the cosmology interest node.

-- ── 1. Repair doubled apostrophes in subtopics_json ─────────────────────────
-- 01_curriculum.sql wrote the `subtopics` JSONB inside $$…$$ dollar-quoting but
-- used SQL '' apostrophe-escaping in the titles. Escaping only applies inside
-- '…' literals, so inside the dollar-quoted block the doubled quotes were
-- stored verbatim ("Newton''s laws", "Coulomb''s law", …). These titles surface
-- as concept-tour tiles and skill-tree node-panel subtopics, so the artefact is
-- user-visible. Collapse every '' back to a single ' in the stored titles.
-- Idempotent: once repaired no '' remains, so the WHERE clause stops matching.
update public.nodes
set subtopics_json = replace(subtopics_json::text, '''''', '''')::jsonb
where subtopics_json::text like '%''''%';

-- ── 2. Correct the Cosmology & Lambda-CDM prerequisite edges ────────────────
-- Seeded prereqs were classical-mechanics, electromagnetism-1, thermodynamics.
-- electromagnetism-1 is not a cosmology prerequisite — its subtopics (Coulomb's
-- law, Biot–Savart, RLC circuits) are irrelevant noise in the concept tour —
-- while the genuine prerequisites statistical-mechanics (CMB, nucleosynthesis)
-- and the relativistic framing were missing. Drop the EM edge, add the two real
-- prerequisites plus multivariable-calculus, and link general relativity as a
-- related (not prerequisite) topic so it shows up as adjacent without dragging
-- its advanced subtopics into the foundation-level tour.

-- Drop the spurious electromagnetism-1 → cosmology prerequisite edge.
delete from public.edges
where edge_kind = 'prerequisite'
  and source_node_id = (select id from public.nodes where slug = 'electromagnetism-1')
  and target_node_id = (select id from public.nodes where slug = 'cosmology-lambda-cdm');

-- Add the genuine prerequisites (statistical mechanics + multivariable calculus).
insert into public.edges (source_node_id, target_node_id, edge_kind)
select s.id, t.id, 'prerequisite'
from public.nodes s
cross join public.nodes t
where t.slug = 'cosmology-lambda-cdm'
  and s.slug in ('statistical-mechanics', 'multivariable-calculus')
on conflict (source_node_id, target_node_id) do nothing;

-- Link general relativity as a related (adjacent) topic.
insert into public.edges (source_node_id, target_node_id, edge_kind)
select s.id, t.id, 'related'
from public.nodes s
cross join public.nodes t
where s.slug = 'general-relativity'
  and t.slug = 'cosmology-lambda-cdm'
on conflict (source_node_id, target_node_id) do nothing;
