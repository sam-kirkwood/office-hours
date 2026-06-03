# Seed interest nodes

Operator-curated interest nodes for the shared megagraph. Each YAML file
in this directory defines one interest node plus its prerequisite and
related edges. Loaded into Postgres by
[`scripts/seed_megagraph.py`](../../../scripts/seed_megagraph.py).

Nodes seeded from here are marked `created_by_user_id = NULL` —
distinguishing them from user-grown nodes created via
`/add-interest/resolve` during the survey dialog. The weekly curation
report ignores `NULL`-created rows; seed nodes are immune to merge /
split / rename proposals by convention.

## File format

```yaml
slug: kebab-case-ascii                  # unique across all nodes
title: Title Cased Display Name         # unique case-insensitively
domain: math                            # math | physics | applied
difficulty_hint: core                   # intro | core | advanced

description_md: |
  Two or three sentences of plain markdown. Capture what the topic IS
  and why someone would care, not what level it's taught at. No LaTeX
  in the description — leave equations for the problem context.

subtopics:                              # 4–8 display names, NOT slugs
  - Subtopic one
  - Subtopic two
  - Etc

prereq_slugs:                           # must match existing nodes
  - calculus-2

related_slugs:                          # optional; produces 'related' edges
  - real-analysis
```

## Authoring workflow

For a brand-new topic the loader script doesn't help with — operator
writes the YAML directly. Three places to anchor the prose:

1. **Description.** 2-3 sentences. Lead with what the topic *is*; close
   with why a working scientist or quant would want to spend time on
   it. Aim for the register of the existing files, which match what
   Sonnet produces via `/add-interest/resolve`.

2. **Subtopics.** 4-8 display names, each 3-6 words. These are the
   chunks a user would recognise as the major conceptual divisions of
   the topic. Concept tours at survey Stage 5 surface these as tiles
   for prerequisite nodes.

3. **Prereq edges.** Only slugs that exist in the megagraph (the
   loader validates this). Genuine prerequisites only; do not pad. An
   interest with one prereq is fine if that's the truth.

If you want a Sonnet draft to start from, run
`/add-interest/resolve` as yourself with the intent text you'd want
the seed to capture, copy the generated description and subtopics into
a fresh YAML, then run the loader with `--reclaim-slug <slug>` to flip
`created_by_user_id` back to `NULL`. That workflow puts you back in
editorial control while saving the keystrokes.

## Running the loader

```bash
# From repo root
uv run --project api python scripts/seed_megagraph.py --dry-run
uv run --project api python scripts/seed_megagraph.py --apply
```

`--dry-run` lists which YAMLs would be inserted vs updated and which
edges would be added without writing anything. `--apply` actually
writes. Both are idempotent — re-running with the same YAMLs produces
no DB changes.

To reclaim a node a user created via the dialog (set
`created_by_user_id = NULL`):

```bash
uv run --project api python scripts/seed_megagraph.py \
    --reclaim-slug superconductivity
```

## What's currently seeded

The eight Slice-1 v1-demoted interests are the initial batch.
Documented in [SEED_PROPOSAL.md](../../../scripts/persona_walkthrough/SEED_PROPOSAL.md);
additional candidates listed there but not yet authored.

## What this directory is NOT for

- **Foundation nodes** — seeded directly by
  [`20250012_seed_nodes_edges.sql`](../../migrations/20250012_seed_nodes_edges.sql).
  Stable, operator-curated, do not add here.
- **User-grown interest nodes** — created via `/add-interest/resolve`
  during the survey, attributed to a real `user_id`. Those flow
  through the weekly curation surface, not this directory.
- **One-off content tweaks** — if you want to change a description on
  a user-grown node, do it via the admin UI or a one-off SQL, not by
  adding a YAML here.
