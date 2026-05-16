# personas.md

Three personas describing the experience of using the product one month
after signing up. These are the primary design tool for the project: any
feature change or architecture decision should be checked against
whether these three users' journeys still work coherently.

Update this file when the product changes meaningfully. If a persona's
journey no longer makes sense under the new design, either the design
is wrong or the persona needs to be updated to reflect a new intent —
don't quietly let the personas drift out of sync with reality.

## How to use these

When evaluating a feature, ask:
- Would this user notice this feature in their daily use?
- Does this feature serve, ignore, or actively hinder their journey?
- Is the journey still possible if this feature is implemented as
  proposed?

When evaluating a design decision, ask:
- Which persona is this decision optimised for?
- Are the other two personas harmed by it?
- Is there a simpler design that serves all three?

---

## Persona 1: The recovering condensed-matter scientist

**Background.** Working scientist, undergrad physics ~5–10 years ago.
Got pulled into superconductor and semiconductor topics after watching
science-fraud videos (Schön scandal, cold fusion). Realised they could
no longer follow the math in a Wikipedia article on bandgaps. Signed up
to rebuild solid-state intuition methodically.

**Survey answers.**
- Free-text intent: "I want to relearn solid-state physics. I think my
  calc and EM are rusty too. Interested in semiconductors and
  superconductors specifically."
- Mode balance: 60% problems, 40% papers — they want to grind some math
  back into shape, not just read.
- Node ratings: marked classical mechanics and waves/oscillations as
  comfortable; flagged calculus, multivariable, ODEs, E&M I, and QM I
  as "want to refresh."

**What the system did at sign-up.**
- Deduplication on the survey intent created two new interest nodes:
  *Solid-State Physics* and *Semiconductor Physics*. The system spotted
  these as related-but-distinct and linked them.
- Generated prerequisite edges back into the foundations they flagged.
- Queue seeded with refresher-flavoured problems on calculus and ODEs,
  plus a foundational E&M I problem to gauge where they are.

**The first two weeks.**
Heavy on math refreshers — derivative gymnastics, separable ODEs,
gradient and divergence drills. Some E&M problems woven in to show the
math being applied. Their problem hit rate was uneven: they aced the
derivatives, struggled on the ODE problems and used hints on most.

The system noticed the ODE struggle and reinforced — more ODE problems
followed, several easier than the ones they'd struggled with. The user
appreciated this without realising it had happened; the queue just felt
right.

They photographed every solution. About a third of vision parses
needed editing; they got faster at correcting them over time.

**Week 3.**
First paper engagement: one of Schön's original papers on organic
superconductors. The system framed it with a "why this" paragraph
mentioning the methodology controversy, and provided orienting concepts:
*organic superconductor*, *gate-induced superconductivity*, *Meissner
effect*. The Meissner effect they didn't recognise — the system offered
a 5-minute refresher first, which they took.

They read the paper externally, then answered five engagement questions
over two sittings. One question pointed at the lack of experimental
detail; another asked how they'd verify a result like this if they were
a referee. Their answers were thoughtful but tentative on the
experimental-design question. Claude's response engaged with what they
noticed, raised the specific things they hadn't (sample preparation,
reproducibility), and didn't condescend. The exchange went into the
notebook.

They asked one follow-up question in free-form Q&A: "Why was this
specific result so hard to spot as fraud at the time?" Claude
answered in a couple of paragraphs that pulled in context they hadn't
got from the paper. That conversation also went to the notebook.

**Week 3, continued.**
After the Schön paper, they realised they'd genuinely forgotten how
conductors and semiconductors work. They explicitly requested
refreshers: "I want to revisit band structure and electron states."
The system parsed this as a request to add *Band Structure* and
*Electron States in Solids* as interests, deduplicated against the
megagraph, and added new queue items — a mix of conceptual problems
and one classic problem on the Kronig-Penney model.

**Week 4.**
They started moving toward the quantum-mechanics side of solid-state
physics. The system surfaced problems on the finite-potential well
(framed as "bandgap as a potential barrier" in the context paragraph)
and the WKB approximation. Their QM I was rusty enough that they used
hints on most of these; one was tagged with `requested_easier` and a
sibling problem was generated.

A YBCO paper was suggested by the system — based on their interest in
superconductors and adjacent papers other megagraph users had engaged
with (this was post-first-curation, so cross-pollination was active).
The "why this" paragraph mentioned that another user in adjacent areas
had recently engaged with this paper. They read it; it was harder than
they expected; they bookmarked two terms they didn't know
(*spin-charge separation*, *Mott insulator*) for later.

**State at one month.**
- Their skill tree view shows a recognisable terrain:
  - Foundations layer: calculus, multivar, ODEs, E&M I, QM I all marked
    *active*. Classical mechanics, waves/oscillations marked
    *comfortable*.
  - Interests: solid-state physics, semiconductor physics, band
    structure, electron states (all *active*). YBCO appears as
    *bookmarked-adjacent*.
  - Greyed adjacent regions show *topological insulators*,
    *high-Tc superconductors*, *photoemission spectroscopy* — none
    explored yet but visible.
- Notebook has roughly 18 entries: 15 problem attempts (with their
  parsed work and Claude's feedback), the Schön paper engagement with
  its full Q&A, and one YBCO paper engagement.
- Mode balance has drifted slightly toward problems as the system
  picked up on reroll patterns; they haven't noticed.

---

## Persona 2: The paper-follower

**Background.** Working scientist, physics undergrad ~5–10 years ago.
Caught the LIGO announcement and the subsequent papers, wants to
actually follow gravitational wave physics rather than just read pop-sci
articles. Doesn't want to do many problems — they want papers.

**Survey answers.**
- Free-text intent: "I want to follow gravitational wave physics.
  Specifically LIGO, the detection papers, and where the field is going."
- Mode balance: 90% papers, 10% problems.
- Node ratings: comfortable with most undergrad math; flagged QM as
  rusty but didn't care much; marked *special relativity* as "want to
  refresh."

**What the system did at sign-up.**
- Survey intent parsed: created interest nodes *Gravitational Wave
  Physics* and *LIGO* (related-but-distinct). Special relativity was
  already an interest node in the megagraph (demoted from v1
  foundations); they were linked to it as a refresh target.
- Queue seeded heavily with papers — starting with the 2016 detection
  paper as a flagship, plus a couple of lighter background reads on
  interferometry.

**The first two weeks.**
The first paper was the 2016 Abbott et al. detection paper. The "why
this" framing connected it to their stated interest; orienting concepts
covered *strain*, *chirp signal*, *matched filtering*, *binary black
hole inspiral*. They knew chirp and binary inspiral roughly, didn't
know matched filtering — took the refresher.

Read the paper over two evenings. Answered the engagement questions
across three sittings (the multi-session resume worked well — they
came back, the system showed where they were). The questions covered
comprehension (what was detected, how confident), critical (what could
have produced a false signal), and connective (how does this relate to
other gravitational wave detectors that exist or are planned).

Their answers were thoughtful but light on the false-signal question.
Claude's response laid out the actual systematic-error considerations
(seismic noise, instrumental glitches, time coincidence requirements)
without being a lecture; just a colleague filling in what they'd
missed.

They asked a Q&A follow-up about the chirp mass formula's derivation;
Claude walked them through it at a level that assumed undergrad
familiarity with orbital mechanics. The notebook captured it all.

**Weeks 2–3.**
Three more papers from that era. Each engagement took 1–3 sessions.
The system spaced them out so they weren't reading every day — a
rest-day refresher problem (set as the 10% problem mode quota) would
appear instead. They mostly ignored the problems but did one on
gravitational wave strain calculation that they actually enjoyed.

In one of the papers' contexts, they encountered references to general
relativity formalism they only half-followed. They bookmarked *general
relativity*, *Christoffel symbols*, and *geodesic equations*.

**Week 3, mid-week.**
They explicitly requested: "Add general relativity to my interests, and
some intro tensor calculus too." The system created GR as a new
interest node (deduped against existing GR-like nodes in the megagraph;
matched the GR node already there), added *tensor calculus* as a new
interest, drew edges to multivariable calculus (foundation) and linear
algebra (foundation). Queue reassessed — papers on GR's mathematical
structure now in the pipeline.

**Week 4.**
First refreshers started surfacing — for the 2016 detection paper,
about three weeks after they engaged with it. "Remember the chirp mass
formula? How did the matched-filtering technique handle false
positives?" Short, two-question form. They got the first one cleanly,
the second one took a moment of effort to reconstruct. They liked it —
several papers in, they were starting to mix the details up, and the
refresher prompts caught that without making them feel bad about
forgetting.

They also got a cross-pollination suggestion: *Cosmology of Compact
Objects* — anonymously framed as something other users in adjacent
areas had explored. They added it to interests.

**State at one month.**
- Their skill tree view is dramatically paper-flavoured:
  - Foundations: multivariable, linear algebra, classical mechanics
    active. Most other foundations untouched.
  - Interests: gravitational wave physics, LIGO, special relativity
    (now *comfortable*), general relativity (*active*), tensor
    calculus (*active*), cosmology of compact objects (*active*),
    Christoffel symbols and geodesic equations (*bookmarked*).
- Notebook is dominated by paper engagements — six papers, each with
  their answers, Claude's responses, and Q&A. The notebook is the part
  of the product they value most; they've started exporting individual
  entries to share with a friend (export is deferred, so they're
  copy-pasting markdown).
- They've done four problems total. None aggressively. The system has
  not increased the problem rate despite the mode-balance slider's
  default, because their explicit signal (90% papers) outweighs the
  reroll-based adjustments.

---

## Persona 3: The math-itch

**Background.** Working in a technical field (numerical engineering,
say). Math has gotten rusty. Wants to refresh ODEs and complex
analysis. No physics interest. Has a personal curiosity-driven
relationship to math.

**Survey answers.**
- Free-text intent: "I want my ODEs and complex analysis back. No
  physics. Pure math problems are great."
- Mode balance: 100% problems, 0% papers.
- Node ratings: comfortable with calc I and II; flagged ODEs and
  complex analysis as "want to refresh"; ignored physics nodes.

**What the system did at sign-up.**
- Mapped ODEs to the foundation node directly. Complex analysis is an
  interest node in the megagraph (demoted from v1 foundations); they
  were linked.
- Queue seeded with ODE refresher problems and complex-analysis intro
  problems.

**The first three weeks.**
Steady. Problem a day, mostly. They aced the first-order ODE problems
in the first week and the system advanced quickly — second-order
linear, then variation of parameters, then a few systems problems.

Complex analysis problems started a week in: Cauchy-Riemann equations,
contour integration. The first contour integration problem they got
caught on; used hints aggressively; the system reinforced with two
simpler problems before returning to the level they'd been stuck at.

In the context paragraph of one ODE problem, a passing reference to
*Laplace transforms* caught their eye. They bookmarked it. Same with
*Frobenius method* a few days later, which appeared in the context of
a series-solution problem.

**Week 3.**
They got curious about a thing at work: signal processing techniques
their team uses but they don't quite follow. They explicitly added
*signal processing* as an interest. The system created the node,
deduped against the megagraph (it already existed — another user had
seeded it), and drew prerequisite edges to ODEs, complex analysis,
linear algebra, and Fourier analysis (which itself was an existing
interest node).

The queue reassessed: existing ODE and complex analysis problems were
re-tagged with signal-processing relevance where applicable, and new
problems started flowing on *Fourier series* and *the Z-transform*.
They didn't realise this happened mechanically; the daily three just
started looking different.

**Week 4.**
A cross-pollination suggestion appeared: *digital filter design* —
adjacent to signal processing in the megagraph, with the framing that
other users in this area had explored it. They weren't sure they
wanted to commit yet, so they bookmarked it.

A first refresher problem surfaced for a contour integration problem
they'd done in week 2. They got it cleanly this time — the rerun was
a confidence boost.

**State at one month.**
- Their skill tree view is math-only:
  - Foundations: calc I, calc II (comfortable); ODEs, linear algebra,
    probability (active).
  - Interests: complex analysis (active), signal processing (active),
    Fourier analysis (active). Laplace transforms, Frobenius method,
    digital filter design — bookmarked.
- Notebook contains ~25 problem attempts. No paper entries (their
  100% problem balance held).
- The system has never asked them how much time they have. They've
  used the reroll button about a dozen times — usually when the
  surfaced item was longer than they felt like dealing with that
  morning.
- They've never been guilted, never been streaked, never been
  badged. The product is just there when they open it.

---

## Patterns across all three

A few things show up in every journey, worth keeping as explicit
design touchpoints:

1. **Free-text interest expression drives everything.** Each persona's
   journey starts with a sentence in their own words, not a
   checkbox-driven curriculum selection.
2. **Cross-pollination is a small but real moment.** All three notice
   the "adjacent users explored this" surface at some point in week 3
   or 4. It's not central, but it's nice.
3. **Refreshers feel valuable, not punitive.** They surface as a
   confidence-building rerun, not a "you forgot this" guilt trip.
4. **The notebook is treasured silently.** None of the personas
   explicitly says "I love the notebook," but all of them end up with
   it being the lasting artefact. User 2 in particular ends up valuing
   it most.
5. **The skill tree view feels like a personal map.** Each persona's
   tree looks meaningfully different — that's the point.
6. **Adaptation is invisible.** None of the personas notices when the
   queue is reweighted; they just notice the daily three feels right.
7. **Explicit requests work.** When a persona wants something specific,
   they can ask for it and the system responds without bureaucracy.
8. **No one is asked how much time they have.** Ever.
