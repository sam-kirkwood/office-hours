# Persona walkthrough #2 — Hank Lindqvist

A second first-session simulation of a brand-new user, run against Phase
10-rev. This one was picked to land squarely inside the physics-and-math
content the product currently supports (the user is told upfront that
problems are only available for physics and math). The first walkthrough
([../persona_walkthrough/WALKTHROUGH.md](../persona_walkthrough/WALKTHROUGH.md))
walked a neuroscientist whose interests fell outside that scope.

This document captures the persona I invented, every input I gave the
system at each stage, every material output I got back, and an honest read.
Raw artefacts under [out/](out/); full persona spec at [persona.md](persona.md).

---

## The persona

**Hank Lindqvist** — 54-year-old senior risk modeller at a quant hedge
fund, semi-retiring in roughly twelve months.

- **Background.** Physics undergrad at Imperial College London, graduated
  1995 (a 2:1 — respectable, not first-class). Did the standard sweep:
  classical mechanics, Lagrangian, E&M I + II, QM I + II, stat mech,
  special relativity, math methods. Went into finance immediately —
  Lehman Brothers in 1996, then 30 years across hedge funds doing
  fixed-income then commodities risk modelling. Has been writing
  Black-Scholes-flavoured PDE solvers and Monte Carlo pricers his entire
  career.
- **What's confident.** Every undergrad math toolkit — multivariable
  calculus, linear algebra, ODEs, PDEs, complex analysis. Probability
  and statistics at the working-quant level: stochastic processes, Itô,
  Girsanov, measure theory at a useful depth. Hand-coded Fortran and
  C++ for production numerical work.
- **What's faded.** Lagrangian mechanics — knows Euler-Lagrange exists,
  couldn't derive a pendulum cold. E&M I — Maxwell's equations in
  differential form requires thinking. QM I — last touched 1995, hasn't
  solved the harmonic oscillator since. Stat mech — knows the partition
  function exists, never properly worked through Maxwell-Boltzmann or
  the Ising model.
- **What he wants.** Statistical mechanics, properly. Partition functions
  through to phase transitions. The Ising model in 1D and 2D. Eventually
  Wilson's renormalization group, then QFT. Has time — semi-retiring next
  year, will do weekends without rushing.

I picked Hank deliberately to be opposite-shaped to Maya: older not
younger, deep math confidence not gaps, rusty on physics not on math,
classical academic on-ramp (stat-mech → phase transitions → RG) not a
cross-disciplinary bridge. He fits the seeded megagraph well — every
foundation he marked refresh is actually in the megagraph; his stretch
interests sit one step beyond stat-mech in a recognisable physics arc.

Full spec at [persona.md](persona.md).

---

## Stage 1 — Background

**Entered.**

Domain chips: **Physics**, **Mathematics**.

Per-domain sub-areas:
- Physics: classical mechanics, electromagnetism, quantum, thermo &
  stat mech, condensed matter
- Mathematics: calculus & analysis, linear algebra, ODEs & PDEs,
  probability & stats

Per-domain relationship cards:
- Physics: *"I studied this and want to reconnect with it"*
- Mathematics: *"I encounter this in my work and want to go deeper"*

Free-text:

> *"Quant taking semi-retirement next year. Physics undergrad 30 years
> ago, been doing applied math in finance since. My math is solid —
> calculus, linear algebra, probability are daily tools — but my physics
> has faded to almost nothing. I want to actually do statistical
> mechanics properly: partition functions, the Ising model, phase
> transitions, eventually renormalization group. I've been using
> Boltzmann distributions analogically in market models for years but
> never derived them from scratch."*

Notable that this signal — *math is daily, physics has faded* — is rare.
Most personas mark math as the gap and treat physics as the reason.
Hank inverts it.

---

## Stage 2 — Foundation tiles

**Entered.** Marked these five as refresh (= `state='active'`):

- classical-mechanics
- electromagnetism-1
- quantum-mechanics-1
- statistical-mechanics
- thermodynamics

Left unmarked (treated as comfortable not-bothering): calculus-1/2,
multivariable-calculus, linear-algebra, ODEs, probability, statistics,
waves-oscillations. These are tools Hank uses daily; he doesn't want to
re-do a chain rule problem.

---

## Stage 3 — Interest suggestions

**Got.**

```
Semiconductor Physics
  why: "Builds on the condensed matter angle you flagged; band structure
        and statistical occupation are partition-function applications."

Cosmology & the Lambda-CDM Model
  why: "Statistical mechanics underpins modern cosmology; phase transitions
        and critical phenomena appear in early-universe physics."

Gravitational Waves & LIGO
  why: "Adjacent to the foundations you flagged."
```

**My read.** A meaningful improvement over what Maya saw. The same three
physics interest nodes — the only ones in the seeded megagraph — but the
rationales are now genuinely on-target:

- Semiconductor Physics: explicitly names *condensed matter* and
  *partition-function applications*. Hank would read this and think
  *yes, Fermi-Dirac statistics, band gaps — I can see the line*.
- Cosmology: explicitly names *phase transitions in early-universe
  physics*. This is exactly Hank's stretch interest area; he'd note it.
- LIGO: the same generic *"Adjacent to the foundations you flagged"*
  fallback as Maya got. Less off-message here because Hank actually has
  classical-mechanics + waves-oscillations as a real foundation
  underneath LIGO, but the rationale doesn't say why.

For Hank, the suggest-interests endpoint works correctly: shortlist
filters by `db_domain='physics'` (he picked physics chips), returns the
physics interest nodes, Haiku reranks with rationales that name specific
intellectual links to his marked stat-mech / condensed-matter sub-areas.
The same code path that misfired for Maya behaves well here. The dead-rail
is specifically a *non-physics-user* failure mode.

Hank's persona ignores the suggestions and types his stretch interests
into the free-text input — he knows what he wants. A different version
of him might bookmark Cosmology after seeing it mentioned, which is the
intended behaviour. The suggestions work.

---

## Stage 4 — Add-interest dialog

Hank types two interests in free-text. Both go through `/parse` and
`/resolve`.

### Interest #1 — Phase transitions and critical phenomena

**Entered.**

> *"Phase transitions and critical phenomena — the Ising model in 1D and
> 2D, mean-field theory, scaling laws, universality classes."*

**Parser response.**

- mirror-back: *"You want to learn phase transitions and critical
  phenomena, with a focus on the Ising model across dimensions,
  mean-field theory, scaling laws, and universality classes."*
- followup: *"Are you approaching this from a statistical-mechanics
  angle, or are you more interested in the broader condensed-matter
  physics picture?"*
- specificity: `specific`. implicit_intent: `teach`. dedup: `related` →
  matched against `statistical-mechanics` (foundation).

**Calibration check.** The mirror-back restates Hank in his own words. The
followup names two real angles for this topic (stat-mech vs condensed-
matter) and reads as a peer-to-peer question. implicit_intent of `teach`
is the correct read — *"I want to learn …"* is textbook teach per the
prompt's rules. The dedup verdict of `related to statistical-mechanics`
is exactly right — phase transitions are taught as part of stat-mech but
deserve their own node at the level Hank wants.

The parser worked correctly here. Notably, this is the second walkthrough
in a row where I'd flag the parser's intent calibration as **good for a
clear "want to learn X" sentence** — and as previously flagged, it
struggles only when the user mixes denial-of-mastery with want-to-learn
language. Hank's sentence is unambiguous.

### Interest #2 — Renormalization group

**Entered.**

> *"Renormalization group — Wilson's approach, fixed points of the RG,
> why it explains critical phenomena, when it works."*

**Parser response.**

- mirror-back: *"You want to learn the renormalization group via Wilson's
  approach — fixed points, how it explains critical phenomena, and its
  scope of validity."*
- followup: *"Are you coming at this from a statistical mechanics angle,
  or more from quantum field theory?"*
- specificity: `specific`. implicit_intent: `teach`. dedup: `related` →
  also matched against `statistical-mechanics`.

The followup is the standout here. RG is real in two contexts —
condensed-matter stat-mech (Kadanoff, Wilson) and quantum field theory
(Gell-Mann–Low, Callan–Symanzik). Asking *which framework* is the right
question to disambiguate. A working physicist asked this would feel
recognised.

### Resolve — new nodes created

Both resolves created new interest nodes:

**Phase Transitions & Critical Phenomena**
- domain: `physics`, difficulty_hint: `advanced`
- description: explicit treatment of *paramagnet→ferromagnet,
  liquid→gas, universal mathematical structure near critical point*,
  builds from *exactly solvable 1D and 2D Ising* through mean-field to
  *scaling laws, critical exponents, and universality classes*. Names
  the actual material.
- subtopics: 1D Ising & transfer matrices · 2D Ising & Onsager solution
  · Mean-field theory & Landau theory · Critical exponents & scaling
  laws · Universality classes & renormalization group · Order parameters
  & symmetry breaking · Correlation functions & diverging length scales
- entry_point_preview: *"A conceptual entry point into why the 1D Ising
  chain never magnetizes at finite temperature — and what that tells us
  about the role of fluctuations in killing long-range order."*

**Renormalization Group & Fixed Points**
- domain: `physics`, difficulty_hint: `advanced`
- description: precise — *systematically integrating out short-scale
  degrees of freedom*, *fixed points of the RG flow govern universality*.
- subtopics: Block-spin and coarse-graining ideas · RG flow equations
  and fixed points · Relevant, irrelevant, and marginal operators ·
  Universality classes and critical exponents · Epsilon expansion near
  four dimensions · Basin of attraction and crossover phenomena ·
  Limitations and breakdown of RG
- entry_point_preview: *"a conceptual entry to Wilson's renormalization
  group — why repeatedly coarse-graining a spin system near its critical
  point always flows toward the same fixed-point Hamiltonian, regardless
  of microscopic details."*

These subtopic lists are *the right list*. Anyone who's taught grad
stat-mech would compose nearly the same. The ε-expansion near 4D and the
*relevant/irrelevant/marginal* classification are exactly the load-bearing
distinctions; no fluff.

**The repeated bug.** Both nodes again have **zero edges** in the
`edges` table. `related_node_slug='statistical-mechanics'` was passed in
for both; statistical-mechanics is a foundation node and is in
`slug_to_node`; the resolve route should have written `related` edges
plus any prereq edges Sonnet proposed. Direct SQL confirms no rows exist
involving either node.

This now reproduces across **three** separate `related`-verdict
resolutions: Maya's dynsys (related to odes), Hank's phase transitions
(related to stat-mech), Hank's RG (related to stat-mech). The pattern is
reliable. Best hypothesis (also flagged in the first walkthrough): the
batched edges-insert at
[add_interest.py:451-456](../../api/routes/add_interest.py#L451-L456)
groups prereq + related rows into one `.insert()` whose error handler
swallows unique violations. If any single row in the batch conflicts —
e.g. Sonnet returns `statistical-mechanics` in
`proposed_prerequisite_slugs` *and* it's the `related_slug` — the whole
batch rolls back and no breadcrumb is logged. Splitting into per-row
inserts + a `logger.warning` would surface this.

For Hank specifically, the consequence is identical to Maya's: both
stretch interests render as orphans on the Stage 7 confirm screen,
disconnected from the stat-mech and thermodynamics foundations underneath
them. Visually incoherent; functionally invisible to downstream surfaces
that walk edges.

---

## Stage 5 — Concept tour

Both concept tours returned **0 tiles**. Direct consequence of the
zero-edges issue. The Stage 5 confirmation tile grid would be empty for
both interests.

---

## Stage 6 — Mode balance

Set to **0.5** (default 50/50). Hank wants both — papers because he
reads them daily anyway, problems because he wants the math.

---

## Stage 7 — Confirm

**Hank's slice.**

```
(foundation) classical-mechanics                   active
(foundation) electromagnetism-1                    active
(foundation) quantum-mechanics-1                   active
(foundation) statistical-mechanics                 active
(foundation) thermodynamics                        active
(  interest) phase-transitions-critical-phenomena    unseen   [INTEREST]
(  interest) renormalization-group-fixed-points      unseen   [INTEREST]
```

**1-hop adjacent (10 nodes).**

```
(foundation) calculus-1                         (foundation) calculus-2
(foundation) linear-algebra                     (foundation) multivariable-calculus
(foundation) odes                               (foundation) probability
(foundation) waves-oscillations
(  interest) cosmology-lambda-cdm
(  interest) gravitational-waves-ligo
(  interest) semiconductor-physics
```

**My read.** Hank's confirmation surface is markedly richer than Maya's,
even though the same orphan-edges bug affects his interests. The
foundations layer is dense (five physics foundations all active), and
the 1-hop adjacent includes the three other physics interest nodes plus
the entire undergrad math toolkit underneath. Hank looks at this and sees
a recognisable physics grad-student graph — he'd intuitively trace lines
from `statistical-mechanics → semiconductor-physics` and `classical-
mechanics → gravitational-waves` and feel oriented.

The two new interest nodes float without explicit edges to the
foundations, which is visually wrong, but at least the foundations they
should connect to are right there in his slice.

For a physics-shaped user, the Stage 7 surface works well even with the
edge bug. For Maya it didn't, because her interests sit in a region the
seeded megagraph has nothing to anchor them against.

---

## Cold-start curator

```json
{
  "plan_queue_items_added": 7,
  "plan_queue_items_reprioritised": 0,
  "plan_queue_items_skipped": 0
}
```

**The 7 items queued, with title and rationale (excerpted):**

| # | kind | content | added_reason |
|---|---|---|---|
| 1 | problem | *"What makes a phase transition singular"* [Ising 1D entry] | "This is your entry point into phase transitions — the 1D Ising model is exactly solvable and builds the intuition (spins, coupling, free energy) that everything else in this topic depends on." |
| 2 | refresher | phase-transitions interest node | "Mean-field theory and the Ising model both lean heavily on partition function manipulations — a quick refresh now means you won't hit a wall mid-problem." |
| 3 | problem | **same as #1** | "Mean-field theory is the conceptual core of this topic — it gives you your first real phase transition, a critical temperature, and the order parameter idea that scaling laws and universality are built on." |
| 4 | problem | **same as #1** | "Once you have mean-field theory, critical exponents (β, γ, ν, …) and the scaling hypothesis are the natural next step — these are the observables that universality classes are actually defined by." |
| 5 | problem | *"What Does Coarse-Graining Reveal About Critical Systems"* [RG entry] | "The block-spin construction on the 1D Ising model is Wilson's RG at its most transparent — a perfect first encounter with fixed points, relevant/irrelevant directions, and why they control universality." |
| 6 | refresher | RG interest node | "RG fixed-point analysis is really a linearisation problem — brushing up on fixed points and eigenvalue stability now will make the RG flow equations feel natural rather than abstract." |
| 7 | problem | **same as #5** | "This is where RG explains universality: why wildly different physical systems share the same critical exponents. It's the conceptual payoff of everything built before it — good to have it queued as something to aim for." |

**My read on the rationales.** Every added_reason is excellent in
isolation. Each names specific concepts a physicist would recognise
("critical exponents (β, γ, ν, …)", "block-spin construction", "relevant/
irrelevant directions", "fixed points and eigenvalue stability") and
each frames the item against where it sits in the syllabus. The look-
ahead refresher #6 specifically names linear algebra (fixed points and
eigenvalue stability) as the prereq for RG — which is exactly what
[curriculum-curator-design §10](../../docs/curriculum-curator-design.md)
asks for. The reasons read as if a thoughtful tutor wrote each one.

**My read on the encoding.** This is where the cracks show. Out of 7
queue items, only **4 unique** pieces of content exist:

- *Phase transition problem* — queued 3× (items 1, 3, 4)
- *Phase transition refresher (interest-node)* — 1×
- *RG problem* — queued 2× (items 5, 7)
- *RG refresher (interest-node)* — 1×

The curator's Sonnet output produced multiple `add` recommendations on
each interest with different `subtopic` strings (1D Ising vs mean-field
vs critical exponents for the phase-transitions interest; block-spin vs
universality for RG). Each one pool-hit to the same existing problem.
The dup-pending-skip mechanism the pivot-plan claims to have evidently
isn't catching same-`ref_id` collisions when the recommendations differ
on subtopic.

The duplication here is worse than Maya's run — 3 copies of one problem
vs 2 copies of two problems. Concerning enough that the dup logic should
be audited before any non-test users sign up.

---

## Surface-daily

```
1. problem    — phase transition Ising entry          priority 0.85
2. refresher  — phase-transitions interest node       priority 0.85
3. problem    — phase transition Ising entry (same)   priority 0.6
```

**Hank's "daily three" contains the same problem at slot 1 and slot 3,
with different rationales.** This is the duplicate bug surfacing at the
worst possible place — the user's first-day view. Hank reading slot 3's
reason ("Mean-field theory is the conceptual core…") would tap it
expecting mean-field material, land on the same Ising-domain-wall
problem he was about to open from slot 1, and be confused.

The variety constraint per [§11.3](../../docs/curriculum-curator-design.md)
says *"the three items should not all be the same kind … or from the
same interest"*. The RG problem (different from phase transitions) and
the RG refresher were both available; the conditional-on-linear-algebra
look-ahead from item #6 wasn't surfaced. A correct daily-three for Hank
would be:
- problem: phase-transitions Ising
- problem: RG block-spin (the second unique one)
- refresher: RG linearisation (because it's a concrete look-ahead)

Surfacing the dup instead of the second unique problem is the variety
filter failing because it dedupes on `kind` and `interest` but not on
`ref_id`.

---

## Underlying content

The artefacts in [out/inspect_report.json](out/inspect_report.json)
contain everything below in full.

### Surfaced #1 — phase-transitions problem

Title: *"What makes a phase transition singular"*. Intent `teach`,
difficulty 4 (advanced node — appropriate). Tags:
`['phase-transitions-critical-phenomena', '1d-ising-model-transfer-matrices', 'order-parameters-symmetry-breaking', 'mean-field-theory-landau-theory']`.

**Context (4 paragraphs in full).** Walks Lenz 1920 → Ising's 1925
dissertation → his disappointment and exit from physics → Onsager 1944
2D exact solution with the closed-form `k_B T_c = 2J / ln(1 + √2) ≈
2.269 J` → Kadanoff 1966 block-spin → Wilson 1971-72 RG → Wilson's 1982
Nobel → the universality discovery of the 60s-70s. Every citation is
real; every formula is correct. The Lenz/Ising biographical opening is
particularly nice — Hank read Pais's *Inward Bound* and would recognise
this register immediately.

**Statement (5 sections).**

- Setup: 1D Ising model with spins `s_i = ±1`, energy
  `E = -J Σ s_i s_{i+1} - h Σ s_i`. Introduced with one paragraph of
  prose, no presumption that Hank remembers this.
- Boltzmann weight + partition function + magnetization. Defined cleanly,
  with the units and notation introduced (β = 1/k_B T, etc.).
- The central question: extreme limits at low and high T.
- **Part (a)–(d) — the energy-entropy domain-wall argument.** Walks the
  classic Landau-Peierls calculation: at low T, the single all-up state
  vs the entropy gain from N-1 domain-wall placements gives
  ΔF = 2J - k_B T ln(N-1), which goes negative for any T > 0 at large N,
  proving 1D Ising has no transition. Part (d) extends conceptually
  to 2D where the domain wall is a line, not a point.

This is genuinely one of the most beautiful single calculations in
introductory stat-mech. It establishes the *physical reason* phase
transitions exist (or fail to) without any heavy machinery. Hank's
reaction would be *"yes, this is the calculation I never properly did
in undergrad"*.

**Hints.** Five levels, well-graduated. L1 is the conceptual lemma
(energy vs entropy, F = E - TS); L2 names the framework (Boltzmann
weight, partition function); L3-L4 are mechanical (compute ΔE = 2J,
ΔS = k_B ln(N-1)); L5 calls out the scaling difference between 1D and 2D
which is the conceptual payoff. The hint ladder is doing what hints
should do.

**Pitched correctly?** Yes. Hank has stat-mech marked refresh — but the
problem doesn't presuppose he remembers partition functions; it builds
them up. He has linear-algebra unmarked (= comfortable) — the problem
doesn't need it. The advanced difficulty hint is appropriate because of
the conceptual subtlety of the domain-wall argument, not because of
machinery.

### Surfaced #2 — phase-transitions "refresher"

`ref_id` is the phase-transitions interest node. When tapped,
`/refresher-resolve` will lookup problems at intent='refresh' on this
node, find none (only the teach problem exists), fall through to
concept_review on the same node, and render either a cached brief or
trigger Haiku to generate one. No brief is cached, so this would be the
first generation.

The added_reason promises *"a quick refresh now means you won't hit a
wall mid-problem"* on partition function manipulations — but Hank would
land on a concept brief about phase transitions and critical phenomena
(the interest node), not on partition function content. Same kind/spec
misalignment as Maya's walkthrough. If the curator intended a partition-
function refresh, the ref_id should have been `statistical-mechanics`
(foundation) with the same added_reason text. Encoding doesn't match
intent.

### Surfaced #3 — duplicate of #1

Same problem, different added_reason. No additional content; just a
queue-management mistake that ate one of three valuable surface slots.

### Unsurfaced — RG problem ([inspected separately](out/inspect_report.json))

Title: *"What Does Coarse-Graining Reveal About Critical Systems"*.
Intent `teach`, difficulty 4. Tags include block-spin, RG flow,
relevant/irrelevant/marginal operators, universality classes, basin of
attraction.

**Context (4 paragraphs).** Universality puzzle of the 60s (water +
helium + ferromagnets converging on identical exponents) → Kadanoff 1966
block-spin → Wilson 1971-72 two PRB papers ("Renormalization Group and
Critical Phenomena I & II") → Wilson's Nobel → Wilson-Fisher fixed
point and ε-expansion (Wilson + Fisher 1972 with ε = 4 - d). Every
citation is correct down to journal volume and the formula
ε = 4 - d.

**Statement.** Walks Wilson RG from scratch:

1. Universality puzzle: water at 647 K vs iron at 1043 K both have
   ν ≈ 0.630.
2. Three-step coarse-graining procedure (block + average, rescale,
   renormalize couplings) with the RG map `R_b` defined.
3. Fixed points and scale invariance.
4. Linearised stability matrix `M_ij = ∂K_i'/∂K_j|_{K*}`, scaling
   operators, eigenvalues λ = b^y, classification into relevant /
   irrelevant / marginal.

**Tasks:**
- (a) Conceptual: why few-relevant-directions implies many basins of
  attraction implies universality. 3-5 sentences.
- (b) Eigenvalue arithmetic warmup — iterate the linearised map to get
  δK_n = b^{ny} δK_0.
- (c) **Extract the correlation-length exponent ν.** Three sub-parts:
  iterate until δK ~ 1, use ξ' = ξ/b per step, derive ξ ~ a|δK_0|^{-1/y},
  identify ν = 1/y. Numerical check: y = 1.587 → ν ≈ 0.630, matching
  experiment.
- (d) Universality punchline.

**This is grad-school RG rendered as an entry-point problem.** It builds
every needed concept, asks the user to derive the most important
identity in critical phenomena (ν = 1/y) from first principles, and
closes by matching to the experimental value the problem opened with.
For a working physicist returning to the material after 30 years, this
is exactly the level — assumes calculus, assumes eigenvalue arithmetic
(both Hank uses daily), builds RG-specific apparatus from scratch.

Hank seeing this problem would be impressed. He should have got it as
slot 3 of his daily three; instead he got the phase-transitions problem
twice.

### Unsurfaced — RG look-ahead refresher

`ref_id` is the RG interest node. added_reason names *"linearisation
problem … fixed points and eigenvalue stability"*. This is the
analogue of Maya's conditional-probability refresher: the curator
correctly identified the linear-algebra prerequisite Hank will need and
queued it. But it's encoded as a refresher on the *interest node*
rather than on the `linear-algebra` foundation, so the resolution will
again drop into a concept_review on the RG node rather than on linear
algebra. Same encoding mismatch as Maya's walkthrough.

---

## My honest read

**The generative core is now firmly verified across two distinct
personas.** Both problems surfaced for Hank are exceptional — the
Lenz/Onsager/Wilson history is correct down to formulas, the Landau-
Peierls domain-wall argument is the right pedagogical move, the RG
problem derives ν = 1/y and matches it to experiment. The Sonnet node-
generation produced subtopic lists that any grad-stat-mech instructor
would compose nearly identically. Every added_reason text is calibrated
to Hank specifically: names concepts a physicist recognises, frames each
item against the syllabus arc, surfaces the right look-ahead
prerequisite. The model is doing its job.

**Stage 3 suggestions now work as intended for an in-scope user.** With
Hank picking the physics chip, the same code path that misfired for Maya
returns three plausible suggestions with rationales that name real
intellectual links (band structure + partition functions for
semiconductors; phase transitions in early-universe for cosmology). The
seed-graph thinness still bites — only three interest nodes exist, all
physics — but for a physics user it's enough to feel oriented. The
honest-fallback fix I suggested in
[the first report](../persona_walkthrough/REPORT.md) is still worth
doing for non-physics users, but the surface itself is sound when given
the right inputs.

**The same three rail issues from Maya's walkthrough reappear, two of
them worse.**

1. **Both new interest nodes are orphans** (zero edges).
   `related_node_slug='statistical-mechanics'` was passed in for both;
   neither produced any edges. This now reproduces across three separate
   `related` resolutions. Splitting the edges insert and logging the
   swallowed exception should land cheaply.

2. **The duplicate queue-item bug is the worst it's been.** 3 copies of
   one problem + 2 copies of another = 4 unique items hidden behind 7
   queue rows. Hank's daily three contains the *same problem twice*, in
   slots 1 and 3, with different rationales. The variety filter on
   surface-daily checks `kind` and `interest` but not `ref_id`; the
   curator's dispatch checks pool hits but not whether the resulting
   `(user, problem)` already has a pending queue item. Both should be
   tightened. This one I'd treat as ship-blocking — it's the highest-
   visibility bug in the walkthrough.

3. **Refresher cards still target interest nodes the user hasn't seen.**
   Items #2 and #6 in Hank's queue are `kind='refresher'` with `ref_id`
   pointing at interest nodes (phase-transitions, RG) that Hank has
   never engaged. The added_reasons explicitly cite *foundation*
   material — partition-function manipulations on stat-mech in #2,
   linear-algebra eigenvalue stability in #6 — but the encoded `ref_id`
   points at the interest node, so `/refresher-resolve` will drop the
   user on a concept_review of the interest node, not on a refresher of
   the foundation the reason promised. This is a curator-output-to-DB
   translation problem: the `interest_node` field of the recommendation
   is being used as the ref_id even when the recommendation's `subtopic`
   and `assumed_background` clearly target a foundation.

**One issue from Maya's walkthrough did not recur: the parser intent
miscalibration.** Both of Hank's interests parsed as `teach` correctly.
The fix (add a rule about "denial of current mastery + want-to-learn
language → teach") is still worth landing, but Hank's input was clear
enough that the existing rules worked.

**One-paragraph overall.** Hank would walk through this and have a
*much* better day-1 than Maya. Stage 3 surfaces three plausible physics
interests rather than three baffling ones. The Stage 7 confirmation
shows him a recognisable physics graph because his foundations are dense
in the seeded layer. The first surfaced problem is a beautiful piece of
intro-stat-mech pedagogy with proper history; the look-ahead refresher
on linear algebra would land him on linear-algebra material that's
already comfortable for him (which is fine for a refresher). He'd open
his notebook, start working through the Landau-Peierls argument, and
feel he'd found something real. **Then** he'd notice that slot 3 of his
daily three was the same problem as slot 1 — and that would be his
*"hmm, this is still software"* moment. Not because the content failed
him; because the surface management did. The owner can ship Phase 10-rev
once the dup-pending bug is fixed; the edge bug is next; the refresher-
kind encoding is a slightly bigger refactor but worth doing. The
generative engine is right.

---

## Cost

Eight LLM calls totalling **$0.207** — survey suggest (1) + parse (2) +
resolve (2) + planner Sonnet (1) + problem generation (2). Cheaper than
Maya's walkthrough because there were no abortive runs and one fewer
problem generated.

---

## Artefacts

| File | Contents |
|---|---|
| [persona.md](persona.md) | Hank's spec |
| [walkthrough.py](walkthrough.py) | Driver script (also has a `queue_summary` action) |
| [out/stage1_survey.json](out/stage1_survey.json) | Persisted Stage 1 row |
| [out/stage2_marked_nodes.json](out/stage2_marked_nodes.json) | Foundation marks |
| [out/stage3_suggestions.json](out/stage3_suggestions.json) | Stage 3 Haiku output |
| [out/stage4_parsed.json](out/stage4_parsed.json) | /parse for both interests |
| [out/stage4_resolved.json](out/stage4_resolved.json) | /resolve incl. (empty) tours |
| [out/stage5_tiles.json](out/stage5_tiles.json) | Empty (no tour tiles existed) |
| [out/stage7_slice.json](out/stage7_slice.json) | Hank's slice of the megagraph |
| [out/cold_start_planner.json](out/cold_start_planner.json) | /run-daily-planner outcome |
| [out/surface_daily.json](out/surface_daily.json) | Today's three picks |
| [out/inspect_report.json](out/inspect_report.json) | Full content of every surfaced item |

User row in Supabase auth: `4ca9260e-8b61-4db6-b706-2f7acfcbe781`
(email `hank.lindqvist.persona@example.com`). Not cleaned up.
