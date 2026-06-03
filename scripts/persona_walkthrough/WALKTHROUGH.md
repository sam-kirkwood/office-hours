# Persona walkthrough — Dr. Maya Chen

A first-session simulation of a brand-new user, run against Phase 10-rev as
the last gate before the owner's own validation. This document captures the
persona I invented, every input I gave the system at each stage, every
material output I got back, and an honest read on whether the experience
would feel made-for-her.

The companion [REPORT.md](REPORT.md) is the same material reorganised by
issue. This document is the narrative.

---

## The persona

**Dr. Maya Chen** — computational neuroscience postdoc, year 2 of 3.

- **Background.** Undergrad in molecular biology eight years ago. PhD in
  systems neuroscience three years ago — she spent the doctorate doing
  intracellular electrophysiology in cortical slices, building intuition
  for neural dynamics empirically. Now she's pivoting toward theoretical /
  computational neuroscience for her postdoc — modelling cortical circuits —
  and finding that her math/CS toolkit is the bottleneck.
- **What's confident.** Cellular and systems neuroscience (Hodgkin-Huxley,
  spike sorting, basic LFP analysis), wet-lab statistics (regression, basic
  mixed models), hand-coded Python for data analysis (numpy, pandas,
  matplotlib), reading bio and neuro papers.
- **What's rusty or never had.** Linear algebra (took it once a decade ago,
  hasn't touched eigenvectors since). ODEs — encountered tangentially via
  Hodgkin-Huxley but never solved one properly. Probability beyond intro
  stats; never properly did Bayesian or measure-theoretic. Information
  theory — knows the terms (entropy, mutual information) but never derived
  them. Dynamical systems — knows the words from neuro papers but couldn't
  draw a phase portrait if asked. Machine-learning math — uses sklearn but
  hand-waves the gradient calculus.

I picked Maya deliberately to land somewhere [docs/personas.md](../../docs/personas.md)
doesn't visit. The three personas there are a recovering condensed-matter
physicist, a paper-following GW physicist, and a math-itch ODE refresher.
None of them have a non-physics professional background, none of them pivot
from one science into another, and none of them have a bio-flavoured
intent. Maya is non-physics, mid-career, mid-pivot — three axes the seeded
megagraph was probably never tested against.

The full persona spec lives at [persona.md](persona.md).

---

## Methodology

The `/api/survey/*` Next.js routes use cookie auth (Supabase magic link),
which is awkward without a browser. I drove the Python FastAPI directly with
the shared `INTERNAL_API_TOKEN`, and wrote supporting state (surveys row,
user_node_states, etc.) through the Supabase admin client. The full driver
script is [walkthrough.py](walkthrough.py); raw responses preserved under
[out/](out/).

To bring up the persona's auth row I used the Supabase admin endpoint
`/auth/v1/admin/users`, which fires `handle_new_user()` and creates the
`profiles` row automatically. User id: `4386f329-485a-40e4-b8a4-de57944c5e05`
(email `maya.chen.persona@example.com`).

I walked Maya through Stages 1–7 + cold-start curator + surface-daily +
content inspection. I did not call any grading or submission endpoints; the
brief was an inspection of generated material, not a full attempt loop.

---

## Stage 1 — Background

**What I entered.**

Domain chips: Mathematics, Computation, Biology. (No Physics, no Chemistry,
no Engineering.)

Per-domain sub-areas:
- Mathematics: linear-algebra, odes-pdes, probability-stats
- Computation: machine-learning, scientific-computing, data-analysis
- Biology: neuroscience, molecular-cell

Per-domain relationship cards:
- Mathematics: *"I studied this and want to reconnect with it"*
- Computation: *"I encounter this in my work and want to go deeper"*
- Biology: *"I follow this field and want to engage more actively"*

Free-text background blurb:

> *"Neuro postdoc moving toward computational theory. Linear algebra and
> ODEs are rusty; information theory and dynamical systems are gaps. I read
> neuro papers fluently but the math sections are where I get stuck."*

Written directly into `surveys.background_json` + `surveys.free_text_intent`.

**What I got back.**

This stage doesn't surface anything — it just persists. No issues, row
written, `completed_stages = ['stage1']`. The data is now visible to Stage 3
and the add-interest dialog.

---

## Stage 2 — Foundation tiles

**What I entered.**

Tiles marked refresh (= `user_node_states.state = 'active'`):

| Foundation | Why |
|---|---|
| Linear Algebra | Took it once 10 years ago, never used since |
| Ordinary Differential Equations | Saw HH but never solved one |
| Probability Theory | Beyond frequentist intro, nothing |
| Statistics | Wet-lab basics only, no Bayesian |

Left unmarked: calculus-1/2, multivariable-calculus, all physics
foundations. Maya treats calculus as comfortable-not-bothering and physics
as irrelevant.

**What I got back.**

Four `user_node_states` rows written. Nothing to review — the
acknowledgement is silent. The interesting test will be whether Stage 3's
suggestions and the curator's queue planning actually use these signals.

---

## Stage 3 — Interest suggestions

**What I sent.** A POST to `/survey/suggest-interests` with Maya's three
domain entries (chips + sub-area labels + relationship-card labels) and the
four `marked_foundation_node_ids` from Stage 2.

**What I got back.**

```
Semiconductor Physics
  why: "Builds on linear algebra and ODEs through band structure theory and
        transport equations in materials."

Cosmology & the Lambda-CDM Model
  why: "Adjacent to the foundations you flagged."

Gravitational Waves & LIGO
  why: "Adjacent to the foundations you flagged."
```

**My read.**

Three tiles, all physics, none plausible for a neuroscientist. The Maya
sitting in front of this screen would assume she'd ticked the wrong boxes,
scroll past, and reach for the *"Curious about something specific?"* input.

The root cause is structural: the seeded megagraph contains exactly three
interest nodes, all physics (semiconductors, LIGO, cosmology). When
`suggest_survey_interests.py` filters by `db_domain` derived from chip keys
— math/comp/bio in this case — the filter produces an empty shortlist, and
the fallback at line 99-107 keeps the whole physics pool. The padding-from-
shortlist rationale *"Adjacent to the foundations you flagged"* then lies:
LIGO has no edge to linear-algebra, ODEs, probability, or statistics, but
the string says it does.

This isn't a calibration miss; it's a cold-start gap. Until the operator
seeds non-physics interest nodes (a handful would do — information theory,
dynamical systems, machine-learning fundamentals, statistical inference,
neuroscience), every non-physics persona will hit this dead surface.

The honest version of the fallback string would be *"Available in the
megagraph; not strongly matched to your background — feel free to skip,"*
or return nothing and lean on free-text.

---

## Stage 4 — Add-interest dialog

I had Maya ignore the suggestions and type her two interests into the
free-text input. The script funnels each through `/add-interest/parse` and
then `/add-interest/resolve`.

### Interest #1 — Information theory

**What Maya typed.**

> *"Information theory for neuroscience — entropy and mutual information for
> analysing spike trains."*

**Parser response.**

- mirror-back: *"You want to learn information theory applied to
  neuroscience, specifically entropy and mutual information for spike-train
  analysis."*
- followup: *"Are you coming to this from a neuroscience background, or are
  you building up the information-theory foundations alongside?"*
- specificity: `specific`. implicit_intent: `teach`. dedup: `same` →
  matched against `information-theory-neural-coding` (a node my first failed
  attempt had created earlier — the system correctly deduped the second
  attempt to it).

The mirror-back restates Maya almost verbatim. The followup names two
genuinely different angles she might be coming from — and is the kind of
question a colleague would ask. Calibrated peer-to-peer tone, no
"thank-you-for-your-response" smell. This stage works.

**Resolve response.** Linked Maya's `user_interests` row to the existing
node. The node already had prereq edges to probability + statistics. Concept
tour returned 10 tiles split 5 probability / 5 statistics.

### Interest #2 — Dynamical systems

**What Maya typed.**

> *"Dynamical systems for neural circuits — I want to actually understand
> bifurcations and attractors instead of just dropping the words."*

**Parser response.**

- mirror-back: *"You want to move beyond name-dropping bifurcations and
  attractors — to actually understand how they shape neural circuit
  dynamics."*
- followup: *"Are you working with specific neural models (like Hodgkin–
  Huxley or rate-based networks), or is the theory itself the main draw?"*
- specificity: `specific`. implicit_intent: **`consolidate`**. dedup:
  `related` → matched against `odes`.

The mirror-back here is the strongest string in the survey. It echoes
*"actually understand … instead of just dropping the words"* almost
rhetorically. The followup names Hodgkin–Huxley specifically — Maya's actual
model from her PhD. The system is reading her.

But `implicit_intent = consolidate` is wrong. The prompt's own rules say
consolidate is for *"I want harder problems on X"* / *"go deeper on X"* —
language that asserts existing mastery. Maya's sentence is the opposite: an
explicit denial of mastery (*"just dropping the words"*) plus a desire to
learn. That's textbook `teach`.

The downstream effect is that the persisted `intent_context` on her
user_interests row opens with *"Wants to deepen understanding of dynamical
systems concepts… Seeking conceptual clarity…"* — consolidate-tinted prose.
The problem generator reads this when planning future problems. The first
pass got rescued because the curator overrode `intent='teach'` on its own
recommendation, but the underlying record carries the wrong baseline. Any
generator that reads it raw will pitch problems for a Maya who already has
the apparatus — she doesn't.

I overrode the dialog response in the script (passed `final_intent_text`
with Maya's clarification added) before resolving. The script's override
is at [walkthrough.py:255-263](walkthrough.py) and reads roughly *"Coming
at it from the neuroscience application side — I want to model neural
circuits — but I genuinely don't have this material yet, I want to learn
it."* That's what a real user would type into the followup field.

**Resolve response.** Sonnet generated a brand-new interest node:

| Field | Value |
|---|---|
| slug | `dynamical-systems-neural-circuits` |
| title | Dynamical Systems & Neural Circuit Modeling |
| domain | applied |
| difficulty | core |
| description | three sentences naming fixed points, limit cycles, bifurcations, attractors; FitzHugh–Nagumo, Wilson–Cowan, HH reductions as motivating playground; explicit pitch toward neural circuit dynamics |
| subtopics | Phase plane and vector fields • Fixed points and linear stability • Limit cycles and neural oscillations • Bifurcations (saddle-node, Hopf, SNIC) • Excitability and spike generation • Multi-stable circuits and memory • Nullcline analysis of neural models • Slow-fast decomposition and bursting |
| entry_point_preview | *"A conceptual entry point into why a neuron can be either excitable or oscillatory depending on a single parameter — and what a bifurcation diagram reveals about that transition in the FitzHugh–Nagumo model."* |

The node generation itself is good. Maya would look at this list of
subtopics and feel met — slow-fast decomposition is the actual mechanism
behind bursting in cortical neurons; multi-stable circuits are how working
memory is modelled. The entry-point preview names FitzHugh–Nagumo, which
is the right pedagogical on-ramp.

**The problem: zero edges.** Despite `related_node_slug='odes'` being
passed in and Sonnet's instruction to produce `proposed_prerequisite_slugs`,
no rows were written to the `edges` table for this new node. Direct SQL
query against `edges WHERE source_node_id = '<dynsys-id>' OR target_node_id
= '<dynsys-id>'` returns zero rows. Concept tour for this node returned
zero tiles (the tour walks prereq edges to populate).

The endpoint didn't error. The user_interests row was written. The node
exists. It just has no connections — an orphan in Maya's graph. On the
Stage 7 confirm screen the dynsys node floats alone with no edges back to
the foundations.

My best guess is the batched edges-insert at
[add_interest.py:451-456](../../api/routes/add_interest.py#L451-L456) groups
prereq + related rows into one `.insert()` whose `_is_unique_violation`
handler swallows the failure and silently aborts the whole batch. If
Sonnet returned `odes` in both `proposed_prerequisite_slugs` and was also
the `related_slug`, that duplicate row would tank the batch. Or Sonnet
returned no prereq slugs at all and only the related-edge insert ran,
failing for a different reason. There's no logging on the swallowed
exception so I can't tell which, but a `logger.warning` in the except block
plus splitting the insert per-row would surface and survive future races.

---

## Stage 5 — Concept tour

For each resolved interest, the resolver returned tour tiles. I had Maya
respond per the persona spec, classifying each tile as familiar /
refresh / new.

### Info-theory tour

10 tiles. Maya's responses:

| Tile (foundation: name) | Maya's response | Why |
|---|---|---|
| probability: Probability spaces & events | refresh | basic but rusty |
| probability: Random variables & distributions | refresh | uses them in analysis |
| probability: Expectation & variance | familiar | wet-lab staple |
| probability: Conditional probability & independence | refresh | the gap |
| probability: Law of large numbers & CLT | refresh | knows the words |
| statistics: Point & interval estimation | refresh | regression background |
| statistics: Hypothesis testing | refresh | wet-lab basics |
| statistics: Confidence intervals | refresh | yes but rusty on derivation |
| statistics: Linear regression | refresh | uses it |
| statistics: Bayesian inference | refresh | knows it exists, hasn't done it |

Per-node aggregate: probability gets {refresh: 4, familiar: 1}; statistics
gets {refresh: 5}. Both nodes already at `active` from Stage 2, so the
per-node state doesn't change.

**My read.** The tour structure here actively works against Maya. Five of
the ten tiles are statistics-flavoured (regression, p-values, confidence
intervals) — they're real gaps she has, but they aren't the right prereqs
for *information theory*. Info theory wants probability spaces, marginal
and joint distributions, conditional independence, KL divergence. The tour
walks all subtopics of both prereq nodes uniformly with no relevance filter
for the destination.

Worse: the subtopics Maya most needs orientation on for info theory —
entropy, mutual information, KL — *don't appear in the tour at all*,
because they belong to the interest node itself, not its prereqs. The
spec is internally consistent (tour is at prereq-subtopic level by
design), but the result is that for an interest with very specific
mathematical prerequisites (info-theory needs ~half of probability and
none of statistics), the tour over-covers and off-targets.

Cheap fix: pass the interest title + description to Haiku, ask it to pick
the top 6-10 most-relevant subtopics across the prereq nodes.

### Dynsys tour

0 tiles. Direct consequence of the zero-edges issue from Stage 4. The
endpoint returned an empty array; the route didn't error; the survey UI
would render an empty tile grid.

A real user would see the empty grid and either think the survey was
broken or assume the system had nothing for them. Neither is a good first
impression.

---

## Stage 6 — Mode balance

Set `mode_balance = 0.45` on `surveys`. Per the schema, 0.0 = all problems,
1.0 = all papers — so 0.45 leans a hair toward problems. Maya wants both
(papers are oxygen for a postdoc; problems are the math she needs to drill).

Nothing to inspect.

---

## Stage 7 — Confirm

Queried Maya's slice of the megagraph: her interests + foundation states +
1-hop neighbours.

**Her slice.**

```
(foundation) linear-algebra                        active
(foundation) odes                                  active
(foundation) probability                           active
(foundation) statistics                            active
(  interest) dynamical-systems-neural-circuits     unseen   [INTEREST]
(  interest) information-theory-neural-coding      unseen   [INTEREST]
```

**1-hop adjacent.**

```
(foundation) calculus-1
(foundation) calculus-2
(foundation) classical-mechanics
(foundation) quantum-mechanics-1
(foundation) statistical-mechanics
```

**My read.** The info-theory interest links cleanly to probability +
statistics, which gives Maya a recognisable picture. The dynsys interest
floats — no edges, no foundations underneath it — which means the
confirmation view will show her something visually incoherent. Half of her
graph looks structured; the other half is an orphan.

The 1-hop adjacent list is also slightly off-message: it surfaces
classical-mechanics, QM-I, and stat-mech because they're prereq-linked to
*odes* or *probability* through the seeded physics graph. None of them are
where Maya's discovery surface should point. Not a bug — the system is
correctly showing 1-hop edges — but the cold-start signal is just bad.

---

## Cold-start curator

POST `/run-daily-planner` with `triggered_by='cold_start'`. The wrapper
calls `/plan-queue` (Sonnet) then `/check-deferred` (deterministic).

```json
{
  "job_run_id": "a26022f3-1ed9-4fa0-a073-fe2813367d6f",
  "plan_queue_status": "ok",
  "plan_queue_items_added": 7,
  "plan_queue_items_reprioritised": 0,
  "plan_queue_items_skipped": 0,
  "check_deferred_requeued": 0,
  "check_deferred_kept": 0
}
```

**What got queued (all 7 items):**

| # | kind | ref | added_reason (excerpt) |
|---|---|---|---|
| 1 | refresher | info-theory node | "Shannon entropy is the central tool, and it sits directly on probability. This refresher makes sure that foundation is solid before the concepts get applied to spike trains." |
| 2 | problem | info-theory entry-point problem | "This is the core question in neural coding: how much does a neuron's response tell you about the stimulus?" |
| 3 | refresher | dynsys node | "Bifurcations and attractors — what you want to understand — are built on fixed-point analysis. This refresher lays that groundwork so the dynamical systems content lands properly rather than feeling hand-wavy." |
| 4 | problem | dynsys entry-point problem | "Phase planes are the visual language of neural circuit dynamics — nullclines, trajectories, attractors all live here. A good first problem for building the geometric intuition you're after." |
| 5 | refresher | probability node | "Conditional probability underpins both mutual information and statistical inference on neural data. Worth a quick refresh now since it will show up repeatedly as you work through information theory." |
| 6 | problem | same dynsys problem as #4 | "Saddle-node bifurcations explain how neurons switch from resting to firing — clean, concrete entry point into bifurcation theory with direct neural meaning." |
| 7 | problem | same info-theory problem as #2 | "Going from the theoretical definition of entropy to actually computing it from recorded spike trains is where the quantitative tools you're after come alive." |

**My read.** The added_reason strings are the standout of the whole
walkthrough. Every single one reads as if it were written for Maya:

- *"before the concepts get applied to spike trains"* — names her domain
- *"what you want to understand"* — quotes her stated intent
- *"rather than feeling hand-wavy"* — answers her self-deprecation about
  *"just dropping the words"*
- *"the quantitative tools you're after"* — names her motivation
- *"clean, concrete entry point with direct neural meaning"* — promises
  the kind of problem she wants

The look-ahead refresher on *conditional probability* (#5) is exactly the
prerequisite-look-ahead behaviour
[curriculum-curator-design §10](../../docs/curriculum-curator-design.md)
specifies. The curator reasoned: she's about to work through info theory;
conditional probability will come up repeatedly; queue it now. Working as
designed.

**The issues.**

Items 6 and 7 are duplicates of items 4 and 2 — same `ref_id`, different
`added_reason`. The pivot-plan status block claims the curator has
"duplicate-pending-skip" logic. It evidently isn't firing when two
different recommendation shapes (different `subtopic` values — e.g.
*"Shannon entropy and neural firing rates"* vs *"Mutual information
between stimulus and response"*) both pool-hit to the same existing
problem. Maya's queue has 7 items but only 5 unique pieces of content.

The two "refresher on a never-engaged interest node" cards (#1 and #3) are
a kind/spec misalignment.
[SPEC.md §Refreshers](../../docs/SPEC.md) defines refreshers as *"Spaced
resurfacing of prior content"* — they assume prior engagement. The curator
clearly *wanted* something like "build the foundation before the main
problem", but encoded that as `kind='refresher'` on the interest node
itself.

The clearest case is #1: added_reason talks about probability foundation,
but `ref_id` is the info-theory interest node. When Maya taps it,
`/refresher-resolve` will look up problems at `intent='refresh'` on
info-theory (none exist — only the teach problem #2 lives there), fall
through to `concept_review` on info-theory, generate a brief if one isn't
cached, and render that. The promise in added_reason and the landing
surface don't line up.

Better either to emit `kind='concept_review'` on the interest node (which
is what actually happens at resolve time), or `kind='refresher'` with the
`ref_id` pointing at the foundation node the reason references.

---

## Surface-daily

POST `/surface-daily` selected three items from the queue:

1. Refresher on info-theory node (priority 0.85)
2. Problem #2 — info-theory entry point (priority 0.85)
3. Refresher on dynsys node (priority 0.85)

The variety constraint produced two refresher + one problem instead of a
more mode-balanced pick. With Maya's mode balance of 0.45 (slight
problem-lean), more like 2 problems + 1 refresher would have been the right
read. Both look-ahead-prereq cards (refreshers #1 and #3) crowded the
slate; the dynsys problem (#4) and the probability refresher (#5) didn't
get surface time. The conditional-probability refresher — the most cleanly
useful item in the whole queue — would arguably have been a stronger pick
than the refresher on the as-yet-unseen interest node.

---

## Underlying content

For each surfaced item I went back to the database to read the generated
material in full. Raw output in [out/inspect_report.json](out/inspect_report.json).

### Surfaced item #2 — info-theory problem

Title: *"What Does a Neuron's Firing Pattern Actually Tell Us"*.

- Intent: `teach`, difficulty 3 (moderate)
- Tags: `['information-theory-neural-coding',
   'shannon-entropy-and-neural-firing-rates',
   'mutual-information-between-stimulus-and-response']` — properly tagged
   at subtopic level per
   [survey-and-difficulty-design.md §3.7](../../docs/survey-and-difficulty-design.md).

Context paragraph (three paragraphs in full). Names Shannon's 1948 *A
Mathematical Theory of Communication*, Horace Barlow's 1961 efficient-
coding hypothesis, William Bialek and Fred Rieke's 1990s work on fly
motion-sensitive neurons, their 1997 book *Spikes: Exploring the Neural
Code*, and the field's current use across sensory cortex, motor cortex,
and population coding. Real history. Real citations. Zero historical
decoration.

This is what [§3.2](../../docs/survey-and-difficulty-design.md) calls
*"connective tissue"* — context that situates the question in the
intellectual lineage Maya actually cares about. She would read this and
think *yes, this is the conversation I want to be having*.

Statement structure:

- **Part 1 — intuition before formulas.** Two extreme toy neurons — one
  that always fires zero, one that maps stimulus to spike count perfectly
  — and three subparts asking why one is useless and one is perfect.
- **Part 2 — Shannon entropy.** Defines `H(X) = -Σ pᵢ log₂ pᵢ`, asks Maya
  to compute `H(S)` for a uniform prior, then `H(S|R)` for both toy
  neurons.
- **Part 3 — mutual information.** Defines `I(S;R) = H(S) - H(S|R)`, asks
  her to compute both and explain why MI is a better summary than just
  rate differences.

Every formula is defined before being used. Passes the
[§3.6 practical generation test](../../docs/survey-and-difficulty-design.md)
cleanly given Maya's confirmed background (probability marked active).

Five-level hints, properly graduated. Level 1 is conceptual ("uncertainty
reduction"); level 5 names a precise watch-out for one of the subparts
(*"For Neuron 1, the posterior equals the prior because the response carries
no information about the stimulus"*).

**This problem is excellent.** Maya would solve it over two evenings,
write the entropy calculations into her notebook, and come away
understanding what mutual information actually measures. She'd feel
*met*.

### Surfaced item #1 — info-theory refresher card

When tapped, `/refresher-resolve` will pool-lookup at intent='refresh' on
info-theory, miss (only the teach problem exists), fall through to
concept_review on info-theory, generate a brief inline (no node_concept_brief
is cached yet), render that brief.

The brief would be ~250 words orienting Maya on the topic before she
attempts the entry-point problem. Not a bad UX outcome — but not what
the added_reason promised (probability foundation refresh).

### Surfaced item #3 — dynsys refresher card

Same mechanic. Pool miss → concept_review on dynsys → inline brief
generation → render. With the dynsys node having no concept brief
cached, the user pays the Haiku latency.

### Queue item #4 — dynsys problem (not surfaced today)

Title: *"What a fixed point reveals about a neuron"* (intent: teach, difficulty 3).

Even better than the info-theory problem in my view.

Context paragraph: traces Poincaré's 1880s geometric theory of differential
equations, the 1881 paper *Sur les courbes définies par une équation
différentielle*, Hodgkin & Huxley's 1952 model (Nobel 1963), FitzHugh and
Nagumo's 1961 phase-plane reduction, Marr's 1971 hippocampal persistent-
activity hypothesis, Hopfield's 1982 attractor networks. The
Marr → Hopfield arc is *the* line of intellectual descent Maya cares about
— memory as attractor dynamics is the gateway from her wet-lab work to
the cortical-circuit modelling she wants to do.

Statement: builds bistability from a 1D toy `F(V) = -V(V-1)(V-3)`,
*derives* the linearisation rigorously (writes V = V* + ε, shows
dε/dt ≈ F'(V*)ε), then asks four parts — find fixed points, classify
stability, sketch the phase line, interpret as bistability/working-memory.
Closes with *"You do not need to use any calculus beyond the product
rule and exponential functions. Algebra and careful reasoning are
sufficient."* — the
[§5 peer-to-peer register](../../docs/survey-and-difficulty-design.md),
no condescension.

If Maya saw this on day one she'd email a friend about the product. It's
that good.

### Queue item #5 — conditional-probability refresher (not surfaced today)

The look-ahead I called out above. added_reason: *"Conditional probability
underpins both mutual information and statistical inference on neural data.
Worth a quick refresh now since it will show up repeatedly as you work
through information theory."* This is the curator doing exactly what
[curriculum-curator-design §10](../../docs/curriculum-curator-design.md)
asks for — proactive prerequisite surfacing before it's needed.

---

## My honest read

**The generative core is strong.** Both entry-point problems and every
piece of added_reason text are calibrated to Maya specifically. Real
intellectual lineage, real neuroscience framing, peer-to-peer tone, proper
subtopic tags, well-graduated hints, conceptual-entrance pitch. These are
the surfaces that decide whether a user comes back tomorrow, and they're
right. Maya's reaction to the two surfaced problem cards would be the
*"yes, that's exactly what I meant"* moment
[§5.1 *"Knows what you want"*](../../docs/survey-and-difficulty-design.md)
is asking for.

**The rails are confused.** Five distinct issues, none of which are 500s,
all of which would make the front door feel less coherent than the content
behind it.

1. **Stage-3 suggestions are wrong for any non-physics user** because the
   seeded megagraph has only physics interest nodes, and the padding
   fallback labels them "Adjacent to the foundations you flagged" when
   they aren't.
2. **The dynsys node has zero edges**, leaving it an orphan in Maya's
   graph, an empty Stage-5 tour, and a visually incoherent Stage-7
   confirmation. Probable cause is a silent batched-insert failure on a
   unique-violation path with no logging.
3. **The add-interest parser misreads explicit denial of mastery as
   `consolidate`** when it's clearly `teach`. Persists into
   `intent_context`, where any downstream generator will read it raw.
4. **The curator emits `kind='refresher'` on never-engaged interest nodes**
   whose added_reason promises a foundation refresh. Resolution lands
   somewhere else (concept_review on the interest node).
5. **Pool-hit dedup leaks**: two distinct problems each queued twice
   under different recommendation rationales.

Plus two adjacent observations:

- The concept tour for info-theory over-covers statistics (regression,
  p-values) and under-covers probability — the structural breadth-first
  walk doesn't filter for the destination interest.
- The variety constraint on surface-daily produced 2 refreshers + 1
  problem when Maya's mode balance leans toward problems and her queue
  contained two strong unsurfaced problem candidates (the dynsys problem
  and the conditional-probability refresher).

**One-paragraph overall.** Not generic-AI-tutor #437. Closer to *"the
system gets me, but the signposting is a bit confused."* Maya would walk
through a sterile Stage 3 thinking the system hadn't read her, type her
two interests in free-text, watch the dialog mirror her back so cleanly
she'd lean forward, then see her Stage-7 graph show one half structured
and the other half floating — and lose a beat of trust there. She'd open
the first day's three cards, click the entry-point problem, and the
*content* would erase the doubt. The owner can ship Phase 10-rev with
these notes in hand; the four issues that are sub-hour fixes (parse intent
rule, edges-insert split + log, dup queue-item check, refresher-kind gate)
would each tighten the first-day experience for non-physics personas
measurably. The Stage-3 cold-start needs a seed pass on non-physics
interest nodes; that one's bigger but is curatorial work, not engineering.

---

## Cost

Eleven LLM calls across the walkthrough — survey suggest, four parse
calls (two from a first failed attempt I had to redo), two resolve calls,
the planner Sonnet call, three problem-generation calls — totalling
**$0.2286**. Well within the brief's stated $1-3 envelope.

---

## Artefacts

| File | Contents |
|---|---|
| [persona.md](persona.md) | Full persona spec (background, gaps, expected responses) |
| [walkthrough.py](walkthrough.py) | The driver: one function per stage, runnable individually |
| [REPORT.md](REPORT.md) | Structured findings reorganised by issue (companion to this document) |
| [out/stage1_survey.json](out/stage1_survey.json) | Persisted Stage 1 row |
| [out/stage2_marked_nodes.json](out/stage2_marked_nodes.json) | Foundation marks |
| [out/stage3_suggestions.json](out/stage3_suggestions.json) | Stage 3 Haiku output |
| [out/stage4_parsed.json](out/stage4_parsed.json) | /parse responses for both interests |
| [out/stage4_resolved.json](out/stage4_resolved.json) | /resolve responses incl. concept tours |
| [out/stage5_tiles.json](out/stage5_tiles.json) | Tour tile responses |
| [out/stage7_slice.json](out/stage7_slice.json) | Maya's slice of the megagraph |
| [out/cold_start_planner.json](out/cold_start_planner.json) | /run-daily-planner outcome |
| [out/surface_daily.json](out/surface_daily.json) | Today's three picks |
| [out/inspect_report.json](out/inspect_report.json) | Full content of every surfaced item |

User row in Supabase auth: `4386f329-485a-40e4-b8a4-de57944c5e05` (email
`maya.chen.persona@example.com`). Not cleaned up — let me know if you want
it wiped before your own walkthrough.
