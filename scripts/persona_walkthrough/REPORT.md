# Persona walkthrough — Phase 10-rev quality check

**Persona walked:** Dr. Maya Chen — computational-neuroscience postdoc bridging
from wet-lab systems neuro into theoretical/modelling work. Linear algebra and
ODEs rusty; information theory and dynamical systems are real gaps. Survey
intent: *"I'm a neuroscience postdoc trying to move toward theoretical /
computational work. My math is rusty in places I now need it — linear algebra
and ODEs especially — and I want to actually understand information theory and
dynamical systems instead of just dropping the words into my papers."* Domain
chips: Mathematics + Computation + Biology. Stage-2 foundations marked refresh:
linear-algebra, odes, probability, statistics. Mode balance 0.45 (slight
problems lean). Full spec in [persona.md](persona.md).

User id: `4386f329-485a-40e4-b8a4-de57944c5e05`. Total LLM spend across the
walkthrough: **$0.23** over 11 calls. All endpoint payloads + raw responses
preserved under [out/](out/).

---

## Worked well

**Add-interest mirror-back uses Maya's own language verbatim.**

Info-theory: *"You want to learn information theory applied to neuroscience,
specifically entropy and mutual information for spike-train analysis."* —
restates her intent in declarative form, no data-summary smell.

Dynsys: *"You want to move beyond name-dropping bifurcations and attractors —
to actually understand how they shape neural circuit dynamics."* — echoes
*"actually understand … instead of just dropping the words"* almost verbatim.
This is the most personalised string in the survey flow.

**Optional follow-up questions read Maya's framing back at her.**

Info-theory: *"Are you coming to this from a neuroscience background, or are
you building up the information-theory foundations alongside?"*

Dynsys: *"Are you working with specific neural models (like Hodgkin–Huxley or
rate-based networks), or is the theory itself the main draw?"* — names HH
specifically, which is the exact model Maya already half-knows. Calibrated
peer-to-peer register.

**Sonnet-generated node descriptions are tailored.**

Info-theory node description names *Shannon, Barlow, electrophysiology,
sensory and motor systems* — Maya's terrain end-to-end. Subtopics list
includes spike-train representations, bias correction in entropy estimation,
population codes, decoding methods — the actual surface of the field, not a
textbook TOC.

Dynsys node description names *FitzHugh–Nagumo, Wilson–Cowan, Hodgkin–Huxley
reductions* as "the motivating playground". Subtopics include slow-fast
decomposition and bursting, multi-stable circuits and memory — exactly the
neural-application angle she's after.

**Curator added_reason strings are the standout.**

Every queue item has a reason that reads like the curator is talking *to*
Maya. Excerpts (verbatim):

- *"This refresher makes sure that foundation is solid before the concepts
  get applied to spike trains."*
- *"Bifurcations and attractors — what you want to understand — are built on
  fixed-point analysis. This refresher lays that groundwork so the dynamical
  systems content lands properly rather than feeling hand-wavy."* — *"feeling
  hand-wavy"* mirrors her *"instead of just dropping the words"* almost
  rhetorically.
- *"Saddle-node bifurcations explain how neurons switch from resting to firing
  — it's a clean, concrete entry point into bifurcation theory with direct
  neural meaning."*
- *"Going from the theoretical definition of entropy to actually computing it
  from recorded spike trains is where the quantitative tools you're after come
  alive."* — *"you're after"* is the right tone.

This is the strongest signal in the walkthrough that the system gets her.

**Surfaced problem #1 — info-theory entry point.** Title: *"What Does a
Neuron's Firing Pattern Actually Tell Us"* (queue item `8b8664a4`, problem
`a1f37424`, [inspect_report.json](out/inspect_report.json)). Intent `teach`,
difficulty 3, tags
`['information-theory-neural-coding', 'shannon-entropy-and-neural-firing-rates', 'mutual-information-between-stimulus-and-response']`
— properly tagged at subtopic level per
[survey-and-difficulty-design.md §3.7](../../docs/survey-and-difficulty-design.md).

Context paragraph (verbatim, three paragraphs in the original) walks
Shannon 1948 → Barlow 1961 efficient-coding hypothesis → Bialek/Rieke 1990s
information-theoretic analysis of fly motion-sensitive neurons → 1997
*Spikes* book → modern use across sensory and motor cortex. Real history,
real citations, no decorative wrapping — exactly the §3.2 standard of
context as connective tissue.

Statement is structured Part 1 (intuition with two extreme toy neurons —
always-zero, perfect-decoder) → Part 2 (defines H(X), H(S|R), then asks
to compute) → Part 3 (defines I(S;R), asks to compute, then a final
interpretive sentence on why MI is a better summary than rate
differences). Every formula is defined before being used. Passes the
§3.6 practical generation test cleanly given Maya's confirmed background
(probability marked refresh = active).

Hints (five levels): L1 conceptual ("uncertainty reduction"), L2 names
the formulas, L3 procedural, L4 mechanical, L5 a precise watch-out
("the posterior equals the prior for Neuron 1"). Well-graduated; no level
leaks the full answer.

**Surfaced problem #2 — dynsys entry point.** Title: *"What a fixed point
reveals about a neuron"* (queue item `779f9962`, [inspect_dynsys output
above]). Intent `teach`, difficulty 3, tags
`['dynamical-systems-neural-circuits', 'fixed-points-and-linear-stability', 'phase-plane-and-vector-fields', 'multi-stable-circuits-and-memory']`.

Context: Poincaré 1881 *Sur les courbes définies par une équation
différentielle* → Hodgkin–Huxley 1952 (Nobel 1963) → FitzHugh & Nagumo
1961 phase-plane reduction → Marr 1971 hippocampal persistent activity →
Hopfield 1982 attractor networks. The Marr → Hopfield arc is *the* line
of intellectual descent Maya would care about — memory-as-attractor is
the gateway from "I model spikes" to "I model what cortex computes".

Statement: builds bistability from a 1D toy F(V) = -V(V-1)(V-3),
*derives* the linearisation rigorously (writes V = V* + ε, shows
dε/dt ≈ F'(V*)ε), asks parts A-D culminating in interpreting bistability
as a working-memory model. Closes with *"You do not need to use any
calculus beyond the product rule and exponential functions. Algebra and
careful reasoning are sufficient."* — the §5 peer-to-peer register, no
condescension.

**Look-ahead refresher on probability** (queue item `d8fe2f9d`, pending,
not surfaced). added_reason: *"Conditional probability underpins both
mutual information and statistical inference on neural data. Worth a
quick refresh now since it will show up repeatedly as you work through
information theory."* — this is exactly the prerequisite-look-ahead
behaviour spec'd in [curriculum-curator-design §10](../../docs/curriculum-curator-design.md).
The curator reasoned forward: Maya will need conditional probability
shortly; queue it now. Working as designed.

---

## Felt off

**Stage-3 suggestions are wrong for a non-physics user.** Maya picked
Mathematics + Computation + Biology and marked 4 math foundations refresh.
The 3 returned suggestions were:

```
Semiconductor Physics:    "Builds on linear algebra and ODEs through band
                          structure theory and transport equations in materials."
Cosmology & Lambda-CDM:   "Adjacent to the foundations you flagged."
Gravitational Waves & LIGO: "Adjacent to the foundations you flagged."
```

None match a neuroscience postdoc. Root cause: the seeded megagraph has
only 3 interest nodes, all physics
([api/routes/suggest_survey_interests.py:99-107](../../api/routes/suggest_survey_interests.py#L99-L107)
falls through the `if scoped:` branch when no candidates match db_domain,
keeping the whole physics pool). The padding fallback rationale *"Adjacent
to the foundations you flagged"* (line 231) is **false** for cosmology and
LIGO — neither has an edge to linear-algebra, ODEs, probability, or
statistics.

A neuroscience-postdoc persona without the operator's intervention would
look at Stage 3, see three physics tiles labelled "adjacent to your
foundations", click none of them, and rely entirely on the *"Curious about
something specific?"* free-text input.

**add-interest/parse miscalled implicit_intent on dynsys.** Maya's input:
*"Dynamical systems for neural circuits — I want to actually understand
bifurcations and attractors instead of just dropping the words."*

Parser returned `implicit_intent='consolidate'`. This is wrong. The prompt's
own rule says *"'I want harder problems on X' → consolidate"* — Maya isn't
asking for harder, she's explicitly denying current mastery. The phrase
*"instead of just dropping the words"* is textbook "I don't have this".

Downstream effect: the persisted `intent_context` on her dynsys user_interests
row opens with *"Wants to deepen understanding of dynamical systems
concepts…Seeking conceptual clarity…"* — consolidate-tinted prose. The
problem generator reads this when emitting future problems. On *this* pass
the curator overrode by passing `intent='teach'` explicitly in the
recommendation, so the surfaced problem is correctly pitched as teach. But
the underlying record carries the wrong baseline.

**dynamical-systems-neural-circuits node has zero edges.** The resolve call
was made with `related_node_slug='odes'`. The resulting node was inserted
fine, but `edges` table contains no rows where either source or target is
that node. The Stage-7 confirmation shows it floating alone in Maya's slice;
the Stage-5 concept tour returned 0 tiles (because `_concept_tour` walks
prereq edges to populate from).

Plausible cause (not confirmed): the batched-edges insert at
[api/routes/add_interest.py:451-456](../../api/routes/add_interest.py#L451-L456)
groups prereq + related rows into a single `.insert()` whose error handler
swallows unique-violation but rolls back the whole batch. If Sonnet's
`proposed_prerequisite_slugs` overlapped with `related_slug` (both naming
"odes"), the duplicate row would tank the batch and *all* edges would
silently fail. Alternative: Sonnet may have returned no `proposed_prerequisite_slugs`
(empty list is permitted) and the related-edge-only insert path failed
without logging. Worth instrumenting that try/except.

**Refresher cards on never-engaged interest nodes.** Two of three daily
picks are `kind='refresher'` with `ref_id` pointing to interest nodes Maya
has never seen (info-theory-neural-coding, dynamical-systems-neural-circuits).
Per [SPEC.md §Refreshers](../../docs/SPEC.md), refreshers are *"Spaced
resurfacing of prior content"* — they assume prior engagement.

The curator's intent here is sound: "build the foundation before the main
problem" — but the *encoding* is misaligned. The clearest case is queue
item `93730243` whose added_reason says *"This refresher makes sure that
**probability** foundation is solid before the concepts get applied to
spike trains"* — but `ref_id` is the **info-theory** interest node, not
probability. When Maya taps it, `/refresher-resolve` will pool-lookup
problems at `intent='refresh'` on info-theory (none exist), fall through
to a `concept_review` on info-theory, render the cached brief. The promise
in added_reason and the landing surface don't match.

Either emit `kind='concept_review'` on the interest node, or emit
`kind='refresher'` with `ref_id` pointing at the actual foundation node
the reason references.

**Duplicate queue items pointing at the same problem.** Seven items
queued, but two distinct problems appear twice each:

- *"What Does a Neuron's Firing Pattern…"* — queue items `8b8664a4`
  (surfaced) and `4637a41e` (pending), both pointing at problem
  `a1f37424`.
- *"What a fixed point reveals about a neuron"* — queue items `779f9962`
  (pending) and `fd8b338c` (pending), both pointing at the same problem.

The pivot-plan status block claims the curator has "duplicate-pending-skip"
logic. It evidently isn't firing when two different recommendation
shapes (different `subtopic` strings — e.g. *"Shannon entropy and neural
firing rates"* vs *"Mutual information between stimulus and response"*)
both pool-hit to the same existing problem.

**Concept tour for info-theory leans heavily on Statistics tiles.** The 10
returned tiles split 5 probability / 5 statistics. The statistics tiles
include *Point & interval estimation*, *Hypothesis testing*, *Confidence
intervals*, *Linear regression*, *Bayesian inference*. These are real gaps
Maya marked refresh — but they aren't the right prereq tiles for
*information theory*. Info-theory wants probability spaces, marginal/joint
distributions, conditional probability, KL — not frequentist regression
and p-values.

The mismatch is structural: the tour is built from prerequisite *node*-level
edges and walks ALL subtopics of those prereqs. There's no per-tile
relevance filter. Cheap fix: pass the interest title to a Haiku rerank that
picks the top 6-10 most-relevant subtopics across all prereqs.

Meanwhile the subtopics Maya most needs orientation on — entropy, mutual
information, KL divergence — *don't appear in the tour at all*, because they
belong to the info-theory interest node itself, not its prereqs.

**Survey-stage tour for dynsys is empty.** Direct consequence of the
zero-edges issue. Maya would see "Confirm your concepts" → empty tile grid.
The route doesn't error; it returns 0 tour tiles silently. Even with a
clean error the UX would be a dead end.

---

## Broken

- **dynsys node has no edges in the database.** Direct SQL confirmed:
  ```
  SELECT * FROM edges WHERE source_node_id = '<dynsys-id>' OR target_node_id = '<dynsys-id>';
  -- 0 rows
  ```
  See `/tmp/walkthrough/check_dynsys.py` output earlier in the session.
  Endpoint did not return an error.

- **No 500s, no malformed responses, no short-circuits seen.** Every
  endpoint returned 200 with valid JSON. The cost ($0.23 / 11 calls)
  matches expectations.

---

## Suggested fixes

**Cheap inline:**

1. **Honest fallback rationale** in
   [suggest_survey_interests.py:231](../../api/routes/suggest_survey_interests.py#L231).
   When padding from an unfiltered shortlist after the domain scope was
   empty, replace *"Adjacent to the foundations you flagged."* with
   something like *"Available in the megagraph; not strongly matched to
   your background — feel free to skip."* Or return no padded suggestions
   at all when the domain-filtered shortlist was empty, leaning on the
   free-text input. Don't claim adjacency that isn't there.

2. **Parse intent rule expansion.** Add to
   [prompts/add_interest.py:69](../../api/prompts/add_interest.py#L69):
   *"Explicit denial of current mastery + want-to-learn language → teach,
   not consolidate. Examples: 'I want to actually understand X', 'I want
   to stop hand-waving X', 'I want to know X properly instead of just
   referencing it' → all teach."* Costs one line of prompt; would have
   caught Maya's dynsys case.

3. **Split the edges insert.** In
   [add_interest.py:451-456](../../api/routes/add_interest.py#L451-L456),
   either insert prereq and related rows separately, or dedupe `edge_rows`
   by `(source_node_id, target_node_id)` before sending. Currently a single
   bad row tanks the entire batch silently. Add a `logger.warning` on the
   swallowed unique violation so future races leave a breadcrumb.

**Note for follow-up:**

4. **Cold-start megagraph diversification.** Seed 8-10 interest nodes
   beyond the 3 physics ones — information theory, dynamical systems,
   machine-learning fundamentals, statistical inference, neuroscience,
   maybe two engineering interests. Otherwise any non-physics persona
   hits the same dead Stage-3 surface Maya did. This is in the spirit of
   what graph-design.md calls out for early product life. Cheap once the
   slugs and subtopics are chosen; the operator can seed by hand.

5. **Curator dup-pending-skip refresh.** In `api/routes/curator.py`, after
   computing a pool hit, check
   ```python
   queue_items WHERE user_id = X
                AND ref_id = problem_id
                AND state IN ('pending', 'surfaced')
   ```
   before inserting. Don't allow the same problem to be queued twice
   under different recommendation rationales. Pick the strongest rationale
   and discard the duplicate.

6. **Refresher kind on never-engaged interest nodes.** Either:
   - in the curator, gate emission of `kind='refresher'` on
     `user_node_states.engagement_count > 0` for the target node, OR
   - re-route the recommendation: if the reason cites a prerequisite
     foundation, emit the refresher on that foundation node's id.
   The current behaviour produces queue cards whose added_reason promises
   one thing and whose resolution lands somewhere else.

7. **Concept tour relevance rerank.** Pass the resolved interest's
   title + description to a Haiku call that picks the most-relevant 6-10
   subtopics across all prereq nodes. The current breadth-first walk
   surfaces statistics tiles for an information-theory interest, which
   confuses rather than orients.

---

## Overall read

For Maya specifically — once she gets to the actual surfaced problems —
this would feel like *"the system gets me."* The two problem cards
([info-theory entry point](out/inspect_report.json) and [dynsys fixed
point](out/inspect_report.json)) are exceptional: both built from scratch
in her field, both framed with real historical lineage (Shannon → Barlow →
Bialek for info theory; Poincaré → FitzHugh-Nagumo → Hopfield for dynsys),
both pitched precisely against her confirmed background, both passing every
[survey-and-difficulty-design §3.2-3.4](../../docs/survey-and-difficulty-design.md)
check. The added_reason strings on every queue item read her own
self-deprecating language back at her *("rather than feeling hand-wavy",
"what you want to understand")*. The proactive refresher on conditional
probability is exactly the prerequisite-timing behaviour curriculum-curator
spec'd. The core generative work is strong.

The gaps are at the rails, not the engine. Stage-3 suggestions are wrong
for any non-physics user because the seeded megagraph is too physics-heavy
and the fallback rationale lies about adjacency. The dynsys node is an
orphan in her graph because edges silently failed to insert. The add-interest
parser misreads "want to actually understand" as consolidate when it's
clearly teach. The concept tour mixes regression-flavoured statistics with
info-theory prereqs in a way that wouldn't help her. The daily surface
emits refresher cards on never-engaged interest nodes whose added_reason
promises probability content but whose resolution lands on the interest
node itself. None of these would crash on her, but they'd hand her a
confused front door before she clicks into the genuinely good content
behind it.

Not generic-AI-tutor #437. Closer to *"the system gets me, but the
signposting is a bit confused."* The owner can ship Phase 10-rev with these
notes in hand; none of them are blockers, but four of the seven would each
take an hour or less to land and would tighten the first-day experience for
non-physics personas materially.
