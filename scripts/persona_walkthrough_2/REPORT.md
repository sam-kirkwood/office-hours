# Persona walkthrough #2 — Phase 10-rev quality check

**Persona walked:** Hank Lindqvist — 54-year-old senior risk modeller at a
quant hedge fund, semi-retiring in ~12 months. Physics undergrad at Imperial
College 1995, 30 years writing Black-Scholes-flavoured PDE solvers and
Monte Carlo pricers since. Math (calculus, linear algebra, ODEs,
probability) is daily bread; physics (classical mechanics, E&M, QM, stat
mech) faded after undergrad. Survey intent: *"Quant taking semi-retirement
next year… My math is solid — calculus, linear algebra, probability are
daily tools — but my physics has faded to almost nothing. I want to
actually do statistical mechanics properly: partition functions, the Ising
model, phase transitions, eventually renormalization group."* Domain chips:
Physics + Mathematics. Stage-2 refresh marks: classical-mechanics,
electromagnetism-1, quantum-mechanics-1, statistical-mechanics,
thermodynamics. Mode balance 0.5 (default). Full spec in [persona.md](persona.md).

User id: `4ca9260e-8b61-4db6-b706-2f7acfcbe781`. Total LLM spend across
the walkthrough: **$0.2070** over 8 calls. All endpoint payloads and raw
responses preserved under [out/](out/).

Hank is the opposite-shape of Maya from [walkthrough #1](../persona_walkthrough/REPORT.md):
older not younger, deep math confidence not gaps, rusty on physics not on
math, classical academic on-ramp (stat-mech → phase transitions → RG) not
a cross-disciplinary bridge. He fits the seeded megagraph well — every
foundation he marked refresh is in the seed; his stretch interests sit one
step beyond stat-mech in a recognisable physics arc.

---

## Worked well

**Stage 3 suggestions are well-targeted for an in-scope user.** Same three
physics interest nodes as Maya got (semiconductors, cosmology, LIGO — the
only interest nodes in the seeded megagraph), but the Haiku rationales
this time name specific intellectual links to Hank's marked sub-areas:

- *Semiconductor Physics: "Builds on the condensed matter angle you
  flagged; band structure and statistical occupation are partition-function
  applications."* — names condensed matter (which he picked) and partition
  functions (his on-ramp).
- *Cosmology & Lambda-CDM: "Statistical mechanics underpins modern
  cosmology; phase transitions and critical phenomena appear in
  early-universe physics."* — names *phase transitions in early-universe
  physics*, exactly Hank's stretch area.
- *Gravitational Waves & LIGO: "Adjacent to the foundations you flagged."*
  — the same generic padding fallback Maya saw; doesn't articulate why.

The same code path that misfired badly for Maya (returning physics tiles
to a neuroscientist with "Adjacent to the foundations you flagged" as the
rationale) works correctly for a physics-shaped user. Confirms the
Stage-3 issue from walkthrough #1 is specifically a *non-physics-user*
failure mode, not a structural problem with the endpoint.

**Add-interest mirror-back + followup for both interests.** Both of
Hank's free-text inputs parsed cleanly with `implicit_intent=teach`,
`specificity=specific`, and `dedup=related to statistical-mechanics`.
Quotes:

Phase transitions: *"You want to learn phase transitions and critical
phenomena, with a focus on the Ising model across dimensions, mean-field
theory, scaling laws, and universality classes."* Followup: *"Are you
approaching this from a statistical-mechanics angle, or are you more
interested in the broader condensed-matter physics picture?"*

Renormalization group: *"You want to learn the renormalization group via
Wilson's approach — fixed points, how it explains critical phenomena,
and its scope of validity."* Followup: *"Are you coming at this from a
statistical mechanics angle, or more from quantum field theory?"*

The RG followup is the standout — RG is a real concept in both stat-mech
(Kadanoff, Wilson) and QFT (Gell-Mann–Low, Callan–Symanzik). Asking which
framework is the right question to disambiguate; a working physicist
would feel recognised.

The intent miscalibration from Maya's walkthrough did **not** recur. Both
of Hank's inputs were unambiguous *"I want to learn …"* sentences, which
the parser handled correctly per its own rule. The fix I suggested for
Maya (add a rule for *"denial of current mastery + want-to-learn → teach"*)
is still worth landing, but Hank's inputs didn't exercise it.

**Sonnet node generation for both interests.**

Phase Transitions & Critical Phenomena (domain `physics`, difficulty
`advanced`). Subtopics: *1D Ising model & transfer matrices · 2D Ising
model & Onsager solution · Mean-field theory & Landau theory · Critical
exponents & scaling laws · Universality classes & renormalization group ·
Order parameters & symmetry breaking · Correlation functions & diverging
length scales.*

Entry-point preview: *"A conceptual entry point into why the 1D Ising
chain never magnetizes at finite temperature — and what that tells us
about the role of fluctuations in killing long-range order."*

Renormalization Group & Fixed Points (domain `physics`, difficulty
`advanced`). Subtopics: *Block-spin and coarse-graining ideas · RG flow
equations and fixed points · Relevant, irrelevant, and marginal operators ·
Universality classes and critical exponents · Epsilon expansion near four
dimensions · Basin of attraction and crossover phenomena · Limitations
and breakdown of RG.*

Entry-point preview: *"a conceptual entry to Wilson's renormalization
group — why repeatedly coarse-graining a spin system near its critical
point always flows toward the same fixed-point Hamiltonian, regardless
of microscopic details."*

These subtopic lists are *the right list*. Anyone who's taught grad
stat-mech would compose nearly the same. The *relevant/irrelevant/
marginal* trichotomy and *ε-expansion near 4D* are the load-bearing
distinctions; no fluff.

**Curator added_reason strings.** Every one of the seven queue items has
a rationale that names physics concepts Hank would recognise.

- *"This is your entry point into phase transitions — the 1D Ising model
  is exactly solvable and builds the intuition (spins, coupling, free
  energy) that everything else in this topic depends on."*
- *"critical exponents (β, γ, ν, …) and the scaling hypothesis are the
  natural next step — these are the observables that universality
  classes are actually defined by"*
- *"The block-spin construction on the 1D Ising model is Wilson's RG at
  its most transparent — a perfect first encounter with fixed points,
  relevant/irrelevant directions, and why they control universality."*
- *"RG fixed-point analysis is really a linearisation problem — brushing
  up on fixed points and eigenvalue stability now will make the RG flow
  equations feel natural rather than abstract."*

Hank reads physicist prose every day; this register is right. The
look-ahead refresher tying RG to linear-algebra eigenvalue stability is
[curriculum-curator-design §10](../../docs/curriculum-curator-design.md)
working as designed.

**Surfaced problem #1 — phase-transitions Ising entry-point.** Title:
*"What makes a phase transition singular"* (queue item `189987c8`,
problem `55a534f2`, see [inspect_report.json](out/inspect_report.json)).
Intent `teach`, difficulty 4, tags
`['phase-transitions-critical-phenomena', '1d-ising-model-transfer-matrices', 'order-parameters-symmetry-breaking', 'mean-field-theory-landau-theory']`
— properly tagged at subtopic level per
[survey-and-difficulty-design.md §3.7](../../docs/survey-and-difficulty-design.md).

Context (four paragraphs in full). Walks Wilhelm Lenz 1920 → Ernst Ising's
1925 dissertation (his disappointment at finding no 1D transition; his
exit from physics into teaching) → Lars Onsager 1944 2D exact solution
with the closed-form `k_B T_c = 2J / ln(1 + √2) ≈ 2.269 J` →
Leo Kadanoff 1966 block-spin → Kenneth Wilson 1971–72 RG → Wilson's 1982
Nobel → the universality discovery of the 60s–70s (helium near the
lambda point, binary fluid mixtures, ferromagnets sharing exponents).
Every citation correct; every formula correct; Lenz/Ising biographical
opening is the kind of touch Hank would notice from his Pais-reading
undergrad days.

Statement (five sections). Sets up the 1D Ising model from absolute
scratch (defines spins, energy `E = -J Σ s_i s_{i+1} - h Σ s_i`,
Boltzmann weight, partition function, magnetization) without
presupposing Hank's 1995 stat-mech is still loaded. Walks the
energy-entropy intuition via `F = E - TS`. Then the **Landau-Peierls
domain-wall argument**: compares the all-aligned state with a single
domain wall, computes `ΔE = 2J` (one bond broken) and `ΔS ≈ k_B ln N`
(N-1 positions for the wall), gets `ΔF < 0` at large N for any T > 0,
concludes the 1D Ising model has no finite-temperature transition. Part
(d) extends the argument to 2D by noting the domain wall becomes a line
whose energy scales with its length — flipping the scaling.

This is one of the most beautiful single calculations in introductory
stat-mech. It establishes the *physical reason* phase transitions exist
(or fail to) without any heavy machinery. Hank would do this over a
weekend and come away understanding the energy-entropy competition
properly for the first time.

Hints (five levels): L1 conceptual (energy vs entropy, free energy
direction); L2 framework (Boltzmann weight, partition function); L3-L4
mechanical (compute the two pieces of ΔF separately); L5 calls out the
scaling difference between 1D and 2D — the conceptual payoff of part
(d). Well-graduated.

**Pitched correctly?** Yes. Hank has stat-mech marked refresh, but the
problem doesn't presume he remembers partition functions; it builds
them. He has linear-algebra unmarked (= comfortable); the problem
doesn't need it. The advanced difficulty rating reflects conceptual
subtlety, not machinery. Passes the
[§3.6 practical-generation-test](../../docs/survey-and-difficulty-design.md)
cleanly given his confirmed background.

**Unsurfaced — RG problem.** Title: *"What Does Coarse-Graining Reveal
About Critical Systems"* (queue items `06ffe800` + `620ac210`, pending,
both pointing at problem `2bd95a6c`). Intent `teach`, difficulty 4.
Tags include block-spin, RG flow + fixed points, relevant/irrelevant/
marginal operators, universality classes, basin of attraction.

Context (four paragraphs). Opens with the universality puzzle of the
1960s (helium, binary fluids, ferromagnets converging on identical
exponents), Landau mean-field theory predicting the wrong but
internally-consistent exponents. Kadanoff 1966 block-spin → Wilson
1971–72 two *Physical Review B* papers (*"Renormalization Group and
Critical Phenomena I & II"*) → Wilson's Nobel → Wilson-Fisher fixed
point and ε-expansion (Wilson + Fisher 1972, ε = 4 - d).

Statement walks Wilson RG from scratch:
1. Universality puzzle reframed: water near liquid-gas critical point
   (647 K, 218 atm) vs iron near Curie temperature (1043 K), both with
   ν ≈ 0.630.
2. Three-step coarse-graining procedure: block-average → rescale →
   renormalize couplings. Defines the RG map `R_b`.
3. Fixed points and scale invariance.
4. Linearised stability matrix `M_ij = ∂K_i'/∂K_j|_{K*}`; scaling
   operators; eigenvalues `λ = b^y`; classification into relevant
   (`y > 0`), irrelevant (`y < 0`), marginal (`|λ| = 1`).

Tasks:
- (a) Why few-relevant-directions implies universality — 3-5 sentences.
- (b) Eigenvalue arithmetic warmup: iterate the linearised map to get
  `δK_n = b^{ny} δK_0`.
- (c) **Derive `ν = 1/y` from first principles.** Three sub-parts:
  (i) find `n*` for `|δK_{n*}| ~ 1`, (ii) combine with `ξ' = ξ/b` per
  step to get `ξ ~ a|δK_0|^{-1/y}`, (iii) identify `ν = 1/y`,
  numerically check with `y = 1.587 → ν ≈ 0.630`, **match to the
  experimental value the problem opened with.**
- (d) Universality punchline.

This is grad-school RG rendered as an entry-point problem. For a
working physicist returning to the material after 30 years, it's the
right level — assumes calculus and eigenvalue arithmetic (both daily
Hank tools), builds RG-specific apparatus from scratch, and closes by
matching theory to experiment in three significant figures. Hank seeing
this problem would be impressed.

This problem should have been surface-daily slot 3. Instead the
duplicate-bug ate that slot (see below).

**Look-ahead refresher on RG → linear algebra** (queue item `c76e22f0`,
pending). added_reason: *"RG fixed-point analysis is really a
linearisation problem — brushing up on fixed points and eigenvalue
stability now will make the RG flow equations feel natural rather than
abstract."* The curator correctly identified the linear-algebra
prerequisite the RG problem will lean on and queued it proactively —
the analogue of Maya's conditional-probability refresher. Working as
[§10](../../docs/curriculum-curator-design.md) specifies.

---

## Felt off

**Refresher cards on never-engaged interest nodes — same kind/spec
mismatch as Maya's walkthrough.** Items #2 and #6 in Hank's queue are
`kind='refresher'` with `ref_id` pointing at interest nodes (phase-
transitions, RG) that Hank has never engaged. The added_reasons each
cite *foundation* material:

- Item #2 added_reason: *"Mean-field theory and the Ising model both
  lean heavily on partition function manipulations — a quick refresh
  now means you won't hit a wall mid-problem."* ref_id =
  phase-transitions interest node. Reason talks about partition
  functions (stat-mech foundation territory); ref_id points at the
  interest node above stat-mech.
- Item #6 added_reason: *"RG fixed-point analysis is really a
  linearisation problem — brushing up on fixed points and eigenvalue
  stability now will make the RG flow equations feel natural rather
  than abstract."* ref_id = RG interest node. Reason talks about linear
  algebra (foundation); ref_id points at the RG interest node.

When tapped, `/refresher-resolve` will look up problems at
`intent='refresh'` on the interest node (none exist — only the teach
problem lives there), fall through to a `concept_review` on the
interest node, render either a cached brief or trigger Haiku inline
generation. The promise in added_reason and the landing surface don't
line up. The intent is right (Hank does need stat-mech partition-
function fluency before the Ising problem; does need linear-algebra
eigenvalue stability before RG); the encoding routes him to the wrong
node.

This is a curator-output-to-DB translation problem. The recommendation
JSON includes both `interest_node` and `assumed_background[]`; the
current pipeline uses `interest_node` as the ref_id even when the
`assumed_background` clearly names what the user needs to refresh. A
recommendation whose reason and assumed-background point at a
foundation should emit `ref_id = <foundation_node_id>`, not
`ref_id = <interest_node_id>`.

**Concept tour empty for both interests.** Direct consequence of the
zero-edges issue (see Broken). Stage 5 confirmation tile grid would be
empty for both phase-transitions and RG. The route returns silently
with `[]`; the user is just shown a blank tour.

**Variety filter on surface-daily.** Hank's daily three contains two
problems and one refresher — but the two problems are *the same problem*.
The variety constraint at
[curriculum-curator-design §11.3](../../docs/curriculum-curator-design.md)
says *"the three items should not all be the same kind … or from the
same interest"* — but doesn't say *"not the same ref_id"*. With three
unique pieces of physics-flavoured content available (the phase-
transitions problem, the RG problem, the look-ahead RG refresher
on linear algebra), the correct surface for a 0.5-mode-balance user
would have been:
- problem: phase-transitions Ising entry
- problem: RG block-spin entry
- refresher: RG → linear algebra (or the phase-transitions refresher)

What Hank got was the phase-transitions problem twice and a refresher.
The variety filter passed because slot 1 and slot 3 are nominally
different queue rows; it should be deduping on ref_id.

---

## Broken

**Both new interest nodes have zero edges in the database.** Direct SQL
query against `edges WHERE source_node_id = '<phase-transitions-id>'
OR target_node_id = '<phase-transitions-id>'` returns zero rows; same
for the RG node. Both `/add-interest/resolve` calls were made with
`related_node_slug='statistical-mechanics'`; statistical-mechanics is a
seeded foundation node and is in `slug_to_node` per the route's own
validation; the resolve route should have written `related` edges plus
any prereq edges Sonnet proposed. None made it to the table.

This now reproduces across **three separate `related`-verdict resolutions**
spanning the two walkthroughs: Maya's `dynamical-systems-neural-circuits`
(related to `odes`), Hank's `phase-transitions-critical-phenomena`
(related to `statistical-mechanics`), Hank's `renormalization-group-
fixed-points` (related to `statistical-mechanics`). The pattern is
reliable.

Best hypothesis (also flagged in
[walkthrough #1's REPORT](../persona_walkthrough/REPORT.md)): the
batched edges-insert at
[api/routes/add_interest.py:451-456](../../api/routes/add_interest.py#L451-L456)
groups prereq + related rows into one `.insert()` whose error handler
swallows unique violations but rolls back the entire batch. If Sonnet
returned `statistical-mechanics` in `proposed_prerequisite_slugs`
(plausible for both phase transitions and RG) *and* it's also the
`related_slug`, the duplicate row sinks the batch and no row gets
inserted. There's no `logger.warning` in the except block so the
swallowed exception leaves no breadcrumb.

**Duplicate queue items are at their worst yet.** Hank's cold-start
curator produced 7 queue items but only **4 unique** pieces of content:

- *"What makes a phase transition singular"* — queue items `189987c8`
  (surfaced slot 1), `217c6d57` (surfaced slot 3), `30dc83e7` (pending).
  Same `ref_id`. Three copies.
- *Phase-transitions refresher* on the interest node — `44310f10`
  (surfaced slot 2). Unique.
- *"What Does Coarse-Graining Reveal About Critical Systems"* — queue
  items `06ffe800` (pending), `620ac210` (pending). Same `ref_id`. Two
  copies.
- *RG refresher* on the interest node — `c76e22f0` (pending). Unique.

**Hank's "daily three" contains the phase-transitions problem at both
slot 1 and slot 3, with different rationales.** This is the duplicate
bug surfacing at the worst possible place — the user's first-day view.
Slot 3's added_reason promises *"Mean-field theory is the conceptual
core of this topic — it gives you your first real phase transition, a
critical temperature, and the order parameter idea …"*; he taps it
expecting mean-field material; he lands on the same Ising domain-wall
problem he was about to open from slot 1. He'd reroll, refresh, or
close the tab.

The pivot-plan status block claims a "duplicate-pending-skip" mechanism
exists. Whatever it checks, it's not catching same-`ref_id` collisions
when the curator's `add` recommendations differ on `subtopic`. The
curator pool-hit-or-generate dispatch evidently doesn't verify
`(user_id, ref_id, state IN ('pending', 'surfaced'))` before inserting
a new queue_items row.

No 500s, no malformed responses. The duplicate-pending bug is the only
behaviour I'd treat as **ship-blocking** — every Hank-shaped user will
hit it on day one.

---

## Suggested fixes

**Ship-blocking / highest-impact:**

1. **Curator dup-pending check.** Before inserting a queue_items row
   from a pool-hit recommendation, check
   ```python
   queue_items WHERE user_id = X
                AND ref_id = problem_id
                AND state IN ('pending', 'surfaced')
   ```
   and if a row exists, skip (or pick the stronger rationale and discard
   the weaker). Without this, every multi-rec-per-interest curator run
   produces duplicates. Same suggestion as
   [walkthrough #1 REPORT.md fix #5](../persona_walkthrough/REPORT.md);
   this run elevates it from a finding to a blocker.

2. **Surface-daily variety filter on `ref_id`.** Surfaces should not
   pick two queue items with the same `ref_id`, regardless of `kind`
   or `interest_node`. Cheap deterministic check inside the variety
   sweep.

**Cheap inline:**

3. **Split the edges insert + log the swallowed exception.** In
   [add_interest.py:451-456](../../api/routes/add_interest.py#L451-L456),
   either insert prereq and related rows separately, or dedupe
   `edge_rows` by `(source_node_id, target_node_id)` before sending. Add
   a `logger.warning` on the swallowed unique-violation so future races
   leave a breadcrumb. Same suggestion as
   [walkthrough #1 REPORT.md fix #3](../persona_walkthrough/REPORT.md);
   the bug now has three confirmed reproductions and is the only outright
   data-loss path in the walkthroughs.

4. **Refresher kind: route to foundation when the recommendation
   targets one.** In the curator's recommendation-to-queue-item
   translation, if a `kind='refresher'` rec has its `subtopic` or
   `assumed_background` naming a foundation node, set
   `ref_id = <foundation_node_id>` rather than the interest node. Same
   issue as
   [walkthrough #1 REPORT.md fix #6](../persona_walkthrough/REPORT.md).

**Note for follow-up:**

5. **Cold-start seed gap for non-physics users.** Same suggestion as
   [walkthrough #1 REPORT.md fix #4](../persona_walkthrough/REPORT.md).
   Not relevant to Hank (physics user), but the same Stage-3 endpoint
   that worked for him misfires for any non-physics user; ~8-10 hand-
   seeded non-physics interest nodes would close that gap. Lower
   urgency now that the "currently only physics and math available"
   copy is in place — but if that copy is intended to be temporary, the
   seed pass becomes urgent again when bio/comp are unlocked.

6. **Honest Stage-3 fallback rationale.** Same suggestion as
   [walkthrough #1 REPORT.md fix #1](../persona_walkthrough/REPORT.md).
   The LIGO suggestion to Hank still used the bare *"Adjacent to the
   foundations you flagged."* rationale, which is less misleading here
   than for Maya (Hank does have classical-mechanics and waves-
   oscillations as adjacent foundations) but still less calibrated than
   the other two suggestions.

**Did not recur from walkthrough #1 (no fix needed this run):**

- Parse intent miscalibration (Hank's two interests were unambiguous
  "want to learn" inputs that the parser handled correctly). Still
  worth landing the rule expansion for users whose phrasing mixes
  denial-of-mastery with want-to-learn language.

---

## Overall read

For Hank specifically — once the duplicate-pending bug is fixed — this
would feel like *"the system gets me"* even more cleanly than it would
for Maya. The seeded megagraph is right-shaped for him (five physics
foundations dense in his slice, three other physics interest nodes
visible at 1-hop adjacent, his Stage-7 confirmation surface coherent
modulo the orphan-edges issue). Stage 3 returns plausible physics
suggestions with on-target rationales rather than wrong-domain padding.
The add-interest dialog reads his physics-shaped intent correctly with
followup questions a colleague would ask (the stat-mech-vs-QFT
disambiguation on the RG question is the standout). The Sonnet node
generation produced subtopic lists indistinguishable from a grad-
stat-mech syllabus. The two generated problems are exceptional pieces
of pedagogical writing — the phase-transitions problem walks Landau-
Peierls cleanly; the RG problem derives `ν = 1/y` from first principles
and matches it to the experimental value `0.630` in three significant
figures. Every added_reason names concepts a physicist would recognise.

The gaps from walkthrough #1 mostly reproduce, with two of them worse:

- **The duplicate queue-item bug is severe this run.** 3 copies of the
  phase-transitions problem + 2 copies of the RG problem out of 7
  queue rows; Hank's daily three contains *the same problem twice*.
  Highest-priority fix.
- **The orphan-edges bug is now confirmed reliable.** Three separate
  `related`-verdict resolves have produced zero-edge nodes; the bug
  needs instrumentation and a per-row insert.
- **The refresher-kind encoding mismatch** still hits — the curator's
  intent for items #2 and #6 is foundation-level material, but the
  ref_id points at the interest node.

One issue **did not** recur: the parser intent miscalibration. Hank's
inputs were unambiguous and the parser handled them correctly. The
rule-expansion fix is still worth landing but isn't load-bearing for
clear-prose users.

The one-paragraph version: Hank would have a *much* better day-1 than
Maya did. Stage 3 surfaces three plausible physics interests rather than
three baffling ones. The Stage 7 confirmation shows him a recognisable
physics graph because his foundations are dense in the seeded layer. He
opens his first surfaced problem and gets a beautiful piece of intro-
stat-mech pedagogy with proper Lenz-Onsager-Wilson history. **Then** he
notices that slot 3 of his daily three is the same problem as slot 1 —
and that's his *"hmm, this is still software"* moment. Not because the
content failed him; because the surface management did. The owner can
ship Phase 10-rev once the dup-pending bug is fixed; the edges bug is
next; the refresher-kind encoding is a slightly bigger refactor but
worth doing. **The generative engine is verified across two distinct
personas now; the rail issues are real but enumerable.**
