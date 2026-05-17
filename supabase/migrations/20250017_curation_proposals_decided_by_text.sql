-- decided_by was created as uuid FK to profiles(id), but the application stores
-- text values (operator email, "system: Invalid node_id", etc.). Drop the FK and
-- change to text.

alter table public.curation_proposals
  drop constraint if exists curation_proposals_decided_by_fkey;

alter table public.curation_proposals
  alter column decided_by type text using decided_by::text;
