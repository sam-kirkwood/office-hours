# Seed megagraph proposal (issue G)

How to close the cold-start gap surfaced by the persona walkthroughs.

The two walkthroughs showed Stage 3 returning the same three physics
interests (semiconductors, LIGO, cosmology) for both an in-scope user
and a non-physics user. Maya saw it as a wrong-domain rail; Hank saw a
working but threadbare surface. The current copy *"problems are only
available for physics and math"* scopes the discoverability question to
those two domains, but even within scope the megagraph is too sparse.

---

## Diagnostic — what's actually there

Direct DB query (`/tmp/walkthrough/check_seed.py`):

```
Interest nodes currently in DB:                            7
  - System-seeded (created_by_user_id = NULL):             0
  - Created by walkthrough/operator-as-user:               7
v1-demoted interests present per ARCHITECTURE.md spec:     0 of 8
```

Two distinct gaps:

**Gap 1 — the documented seed never happened.** ARCHITECTURE.md
§Migration from v1 explicitly says:
> 8 become interest nodes (PDEs, real analysis, complex analysis,
> Lagrangian mechanics, special relativity, E&M II, optics, QM II).

The v1→v2 migration at `supabase/migrations/20250012_seed_nodes_edges.sql`
seeds from `canonical_topics` and sets `kind='interest'` for any slug
*not* in the foundation list. But `canonical_topics` apparently only ever
contained the 13 foundation slugs + 3 physics interests — never the 8
demoted ones. The architecture doc describes an intended state that the
migration never produced.

**Gap 2 — no `created_by_user_id = NULL` convention.** The three
"seeded" physics interests in the DB were actually created by a test
user's dialog flow (user_id `11898e88`). There's no marker
distinguishing system-curated nodes from user-grown ones, which matters
when:

- the weekly curation report asks which nodes need attention
- cross-pollination wants to know which adjacent nodes are
  "always-available" vs "another-user-created"
- the operator wants to clean up after personas without deleting real
  seed content

`nodes.created_by_user_id` is already nullable on the schema; nothing
in code uses NULL as the seed marker today.

---

## Proposed scope

Three slices, each independently shippable. The first two fit inside the
Phase 10-rev close; the third is operator content work that can roll
forward.

### Slice 1 — Backfill the 8 v1-demoted interests

Bug fix, not authoring. ARCHITECTURE.md already names them. Each gets a
short description, 4-8 subtopics, prereq edges to the foundations they
sit on. Authored by hand because they're well-known curriculum items.

| Slug | Domain | Difficulty | Prereqs |
|---|---|---|---|
| `partial-differential-equations` | math | core | calculus-2, multivariable-calculus, odes |
| `real-analysis` | math | core | calculus-2 |
| `complex-analysis` | math | core | calculus-2, multivariable-calculus |
| `lagrangian-mechanics` | physics | core | classical-mechanics, multivariable-calculus |
| `special-relativity` | physics | core | classical-mechanics, electromagnetism-1 |
| `electromagnetism-2` | physics | core | electromagnetism-1, multivariable-calculus |
| `optics` | physics | core | waves-oscillations, electromagnetism-1 |
| `quantum-mechanics-2` | physics | advanced | quantum-mechanics-1, linear-algebra |

Set `created_by_user_id = NULL` on all eight.

**Mechanism.** A new SQL migration `20250029_seed_v1_demoted_interests.sql`
with INSERT statements + edges. Reviewable as a PR. ~2-3 hours of
authoring (most of the time is writing 2-sentence descriptions and the
subtopic lists; the slugs and prereq sets are obvious).

### Slice 2 — Author the seed mechanism for ongoing growth

The migration approach works for fixed lists but doesn't scale. Going
forward the operator should be able to add a seed interest by writing
~5 lines of YAML.

**Proposed shape.** A new directory `supabase/seeds/interests/` with one
YAML file per interest node:

```yaml
# supabase/seeds/interests/superconductivity.yaml
slug: superconductivity
title: Superconductivity
domain: physics
difficulty_hint: advanced
description: |
  Electrical conduction without resistance — the BCS theory of Cooper-pair
  formation in low-Tc superconductors, the unsolved puzzles of high-Tc
  cuprates, and the macroscopic quantum coherence that makes the Meissner
  effect possible.
subtopics:
  - BCS theory and Cooper pairs
  - Meissner effect and flux exclusion
  - Type I and Type II superconductors
  - Josephson junctions and SQUIDs
  - High-Tc cuprates and the gap
  - Ginzburg–Landau theory
prereq_slugs:
  - quantum-mechanics-1
  - statistical-mechanics
  - electromagnetism-1
related_slugs:
  - semiconductor-physics
```

**Plus a thin loader script** `scripts/seed_megagraph.py`:

```
uv run python scripts/seed_megagraph.py --apply
```

Reads every YAML under `supabase/seeds/interests/`, upserts each into
`nodes` (idempotent on slug), and writes `prereq` / `related` edges
(skipping duplicates). Always sets `created_by_user_id = NULL`. Prints a
diff before applying.

**Why YAML over a Sonnet-driven generator.** The walkthroughs showed
Sonnet generates *excellent* node descriptions and subtopic lists when
invoked through `/add-interest/resolve`. The temptation is to reuse that
machinery for seeding. I'd push back:

- **Seed content is the operator's editorial responsibility.** The
  weekly curation report is for cleaning up user-grown nodes; seed
  nodes should be deliberate.
- **YAML is durable.** It survives Sonnet model upgrades; it's
  diff-reviewable; it can be hand-edited.
- **Sonnet is still useful — as a draft tool, not the source of
  truth.** The operator can call `/add-interest/resolve` as themselves,
  copy the generated description and subtopics into a YAML file, edit
  what they don't like, commit. That workflow keeps the LLM in the
  loop without committing its raw output to the seed.

**Effort.** ~4 hours: YAML schema + loader script + tests for
idempotency + 2-3 hand-authored example files to validate the format.

### Slice 3 — Author the actual seed content — ✓ DONE

**Outcome.** The megagraph is now 42 nodes (13 foundation, 29 interest —
all 29 seeded with `created_by_user_id = NULL`), 109 edges (76
prerequisite, 33 related), zero orphan interest nodes, and every domain
clears the Stage-3 `SUGGESTION_MIN = 6` threshold (applied 7, math 7,
physics 15). All candidate slugs below were authored, plus three "unusual"
picks (quantum-information, coding-theory-error-correction,
computational-complexity), and the 3 previously user-created nodes
(semiconductor-physics, gravitational-waves-ligo, cosmology-lambda-cdm)
were reclaimed as seeds. Seven interest↔interest "related" bridges were
added for cross-pollination and a stray gravitational-waves-ligo→cosmology
prerequisite mis-curation was dropped. Snapshot any time with
`uv run --project api python scripts/megagraph_report.py`. Balance note
for a future pass: physics (15) outweighs math (7) and applied (7) — next
authoring should tilt math/applied (optimisation, graph theory, Bayesian
inference, game theory, number theory/cryptography, control theory).

The original plan follows for reference.

What the operator should put in `supabase/seeds/interests/` once Slice 2
exists. Goal: 18–25 total interest nodes covering physics + math
densely enough that Stage 3 surfaces 6-10 plausible suggestions for any
reasonable user.

**Already in the DB (3, keep):** semiconductor-physics, gravitational-
waves-ligo, cosmology-lambda-cdm. Re-do with `created_by_user_id =
NULL` to mark them as seed.

**From Slice 1 (8, backfill).** As listed above.

**Drawn from `docs/personas.md` (high-value because the personas
already justify them):**

- solid-state-physics — Persona 1's primary interest
- band-structure-electron-states — Persona 1, mid-flow
- general-relativity — Persona 2 explicitly adds this
- tensor-calculus-differential-geometry — Persona 2 explicitly adds
- signal-processing — Persona 3 explicitly adds
- fourier-analysis — Persona 3 hits this via signal processing
- digital-filter-design — Persona 3's cross-pollination suggestion

**Drawn from the orphan-claimed nodes — ✓ DONE in Step 9b (all four
persona orphans reclaimed as seeds with `created_by_user_id = NULL` and
backfilled edges):**

- phase-transitions-critical-phenomena (Hank)
- renormalization-group-fixed-points (Hank)
- information-theory-neural-coding (Maya)
- dynamical-systems-neural-circuits (Maya)

**Worth adding to round out coverage:**

- superconductivity — natural neighbour to semiconductor-physics
- chaos-and-nonlinear-dynamics — bridges classical mechanics and
  applied
- numerical-methods-pdes — math-applied, fills the
  "computational-science-y math" gap
- probability-stochastic-processes — math interest above the
  probability foundation (covers what Hank has from quant work)

Brings the total to ~22 nodes — comfortably above the
`SUGGESTION_MIN = 6` threshold for Stage 3 in either domain.

**Effort.** ~1 day for the operator. Each YAML is ~10 lines; the
description + subtopics is the bulk. Sonnet-generated drafts via the
`/add-interest/resolve` route + manual review will speed this up.

---

## Suggested ordering relative to Step 9

**Slice 1** can land alongside the Step 9a/9b/9c commits — it's a
2-3 hour SQL migration. Closes the documented-but-missing gap and
immediately gives the existing UI more to draw from.

**Slice 2** can land in the same phase if you want the future-proof
mechanism in place before opening up. Operator-readable YAML + a
loader script is a small commit.

**Slice 3** is content work that rolls forward — the operator can
seed in batches over a few weeks. The Stage-3 padding-fallback fix
from Step 9c is the safety net during that period: it returns honest
"not strongly matched" suggestions when the seed is still thin in
a domain.

**Cross-pollination caveat.** Cross-pollination uses megagraph
adjacency, so a denser seed automatically makes it surface more.
That's fine — but the cross-pollination spec says it only fires
after the first weekly curation round (per `docs/SPEC.md`), so the
seed growth doesn't risk surfacing under-developed nodes
prematurely.

---

## Operator-as-user fallback

While slices 1–3 are landing, the operator can also use themselves as
a seed user: walk through the survey, type the interests they want as
seed nodes into the free-text input, let the existing
`/add-interest/resolve` flow create them. Nodes created this way live
in the megagraph immediately and are visible to all users via Stage 3.
Downside: they're attributed to the operator's user_id rather than
NULL. If a node was created by the operator first, the YAML loader
should optionally back-fill it (set `created_by_user_id = NULL` on
matching slug) — worth a flag on the loader for cleanup.

---

## What this proposal does *not* do

- **Auto-generate seed content from an LLM.** Authoring stays with the
  operator. Sonnet is a draft tool, not the source of truth.
- **Open up biology/chemistry/computation domains.** That's a separate
  decision tied to the "currently only physics and math" copy. Once
  removed, Slice 3 extends naturally with a `supabase/seeds/interests/
  bio/`, `comp/`, etc. structure.
- **Curate foundation nodes.** Foundations are stable and operator-
  authored already; this is purely about the interest layer.
- **Replace the weekly curation report.** That handles merges/splits/
  renames on user-grown nodes. Seed nodes are immune to those flows by
  convention; the curation report can ignore `created_by_user_id =
  NULL` rows.

---

## Acceptance check — ✓ met

Slice 1 + Slice 2 + Slice 3 have all landed (29 interest nodes, well past
the ~10-node Slice-3 bar). The original acceptance criteria, for the
record:

After Slice 1 + Slice 2 + ~10 nodes of Slice 3 land:

1. Maya's stage3 (without changing her domain picks) returns at least 3
   suggestions that aren't physics — `signal-processing` and
   `numerical-methods-pdes` are the likely top hits via her math
   prereqs. Or, if `bio` domains remain locked, Stage 3 returns
   *honest* "we don't have much in your domains yet — try the free-text
   input" copy via the Step 9c fallback fix.
2. Hank's stage3 returns ≥6 suggestions; `superconductivity`,
   `phase-transitions`, and his RG interest would all surface as
   adjacent to stat-mech.
3. Skill-tree 1-hop adjacent for a fresh user shows 8-15 nodes rather
   than the 3-5 it shows today.
4. Cross-pollination, once enabled, has real candidate density to draw
   from rather than the same three physics interests.
