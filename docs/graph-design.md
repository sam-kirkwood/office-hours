# graph-design.md — The megagraph

This document is the source of truth for how the knowledge graph works in
this project. SPEC.md and ARCHITECTURE.md reference it without duplicating
the design.

## The two-layer model

The graph has two layers of nodes:

- **Foundation nodes** are operator-curated, stable, shared across all
  users. They cover the math and physics that almost any user will draw
  on — calculus, ODEs, linear algebra, classical mechanics, basic E&M,
  basic quantum mechanics, and so on. There are around a dozen.
- **Interest nodes** are user-added, organic, and accumulate over time.
  They cover the specific things working scientists actually want to
  learn — FETs, gravitational waves, unscented Kalman filters,
  topological insulators, diffusion models. There's no cap on how many
  exist; they grow with use.

Both kinds of nodes live in the same `nodes` table with a `kind` column
distinguishing them. Both can participate in edges in either direction.
The conceptual distinction is curation lifecycle, not data structure.

Why this split:

- **Sharing problems is valuable for foundations.** A well-crafted
  Schrödinger-equation-in-a-box problem benefits every user who studies
  it; pooling makes sense and is what justifies the operator curation.
- **Sharing problems is less valuable for niche interests.** A problem
  about FET threshold voltage is bespoke for the user who's learning
  FETs; pooling across many users isn't the goal there (though it can
  still happen if multiple users share that interest).
- **Foundations are stable; interests are fluid.** The foundations layer
  doesn't change much over months; the interests layer changes daily as
  users add things.
- **Operator burden is bounded.** You curate a small foundations layer
  and run a weekly cleanup on the interests layer. You're not
  approving every new interest someone adds.

## The megagraph

The megagraph is the full set of nodes (foundation + interest) and
edges across all users. It's a single shared structure. Every user's
view of "their graph" is a slice of it.

The megagraph grows over time as users add interests. The weekly
curation round keeps it coherent. Snapshots are taken so its evolution
can be visualised over months.

## Foundation nodes

The initial seed of foundation nodes is the v1 canonical curriculum,
shrunk:

| Foundation                                                          | Domain   | Why foundational                                           |
|---------------------------------------------------------------------|----------|------------------------------------------------------------|
| Calculus: Derivatives and Basic Integration                         | math     | Universal prerequisite                                     |
| Calculus: Integration Techniques and Series                         | math     | Series, integration techniques used everywhere             |
| Multivariable Calculus                                              | math     | Partial derivatives, multiple integrals — applied widely   |
| Linear Algebra                                                      | math     | Required for quantum mechanics, signal processing, ML      |
| Ordinary Differential Equations                                     | math     | The math backbone of most physical models                  |
| Probability                                                         | math     | Required for statistics, stat mech, ML, signal processing  |
| Statistics                                                          | math     | Applied widely; needed by many interests                   |
| Classical Mechanics                                                 | physics  | Almost any physics interest builds on Newtonian mechanics  |
| Waves & Oscillations                                                | physics  | Building block for QM, optics, signal processing           |
| Electromagnetism: Static Fields and Maxwell's Equations             | physics  | Building block for the dynamical pass, optics, devices     |
| Thermodynamics                                                      | physics  | Building block for stat mech, condensed matter, chemistry  |
| Statistical Mechanics                                               | physics  | Underlies condensed matter, much of soft matter, ML        |
| Quantum Mechanics: Wavefunctions, Operators, and the Hydrogen Atom  | physics  | Building block for the advanced pass, solid state, HEP     |

13 nodes. The 8 v1 canonical topics not on this list (PDEs, real
analysis, complex analysis, Lagrangian mechanics, special relativity,
E&M II, optics, QM II) are reclassified as interest nodes — still in the
graph, still seeded, but as user-facing interests rather than curated
foundations. They retain their existing prerequisite edges into the new
foundations.

This is a starting set. The weekly curation can promote or demote nodes
as the picture clarifies. A foundation isn't immutable.

## Interest nodes

Created when a user expresses interest in a topic, either at onboarding
or via an explicit request later. Each has:

- A canonical title (e.g., "Field Effect Transistors", not "FETs")
- A slug (e.g., `field-effect-transistors`)
- A short description (1–3 sentences)
- A list of subtopics
- A domain tag (math / physics / applied)
- A difficulty hint (intro / core / advanced)
- The set of edges proposed at creation time (to foundation nodes and to
  other interest nodes)
- Metadata: created_at, created_by_user_id, engagement_count

Interest nodes are *shared* across users via deduplication (see below).
If User A creates "Field Effect Transistors" and User B later expresses
interest in FETs, B is linked to the same node, not a new one.

## Deduplication

When a user adds an interest, the system attempts deduplication at add
time, autonomously. The flow:

1. User submits an interest in free text ("I want to understand FETs",
   "MOSFET behavior in saturation", "field-effect transistors").
2. The system sends a Claude (Haiku) call: "Here are the existing
   interest nodes whose titles, descriptions, or subtopics might match
   this. Is the user's interest the same as one of these, related but
   distinct, or genuinely new?"
   - Pre-filter the candidate list via a simple title-similarity
     search to keep the prompt size bounded.
3. If Claude says "same": link the user to the existing node. Done.
4. If Claude says "related but distinct": create a new node, with an
   edge to the related one. The user sees both.
5. If Claude says "new": create a new node. Trigger a second Claude
   (Sonnet) call to generate the node's description, subtopics, domain,
   difficulty, and proposed prerequisite edges to foundations and to
   other interest nodes.

The user is not asked to confirm. The operator sees the dedup decision
in the weekly curation report and can override if Claude got it wrong.

Edge cases:

- **The user submits something that should be split into multiple
  interests** ("I want to learn solid-state physics and quantum
  computing"). The system prompts Claude to identify the split; the
  user gets multiple interest nodes added at once. The user sees a
  brief "Added these to your interests: X, Y" confirmation.
- **The user submits something too vague** ("I want to learn math"). The
  system responds with a clarifying prompt rather than creating a vague
  node. Vague interests should not pollute the graph.
- **The user submits something that's actually a foundation** ("I want
  to learn calculus"). The system links them to the foundation node
  rather than creating an interest node duplicate.

## Edges

Edges are directed and weighted. They live in a single `edges` table
spanning both layers.

Edge types:

- **Prerequisite edges**: A → B means "A is foundational to B". Created
  by Claude when an interest node is generated; reviewed in weekly
  curation.
- **Related edges**: A ↔ B means "A and B are adjacent without being
  prerequisites." Bidirectional. Created when Claude identifies relevant
  links during interest generation or during weekly curation.

Weights are floats. Higher weight means stronger relationship. Used by
the cross-pollination logic to surface nearby topics.

## Weekly curation

A background job runs weekly. It generates a curation report by calling
Claude with a structured view of recent megagraph changes:

- All interest nodes added in the past week
- All edges added in the past week
- Any deduplication decisions Claude made autonomously
- Aggregate engagement signals (which nodes are getting attention; which
  aren't)

Claude proposes:

- **Merges**: nodes that turned out to be the same and should be unified
- **Splits**: nodes that have accumulated enough engagement across
  distinct subtopics to warrant splitting
- **Renames**: nodes whose title or slug should be standardised
- **Promotions**: interest nodes that are turning up as prerequisites for
  many other interests and might deserve foundation status
- **Demotions**: foundation nodes that have seen little use and might be
  reclassified as interests
- **New edges**: relationships Claude infers from recent activity
- **Deprecations**: nodes that haven't been used in months

The report is stored in `curation_proposals` and surfaced in the
operator admin UI. The operator approves, edits, or rejects each
proposal. Approved proposals are applied to the graph; a snapshot is
taken.

The operator's weekly time on this should be 15–30 minutes for a graph
at this scale. The report should be sortable and bulk-actionable for
trivial cases (e.g., "approve all merges").

## Snapshots and evolution

After every weekly curation round, a snapshot of the full megagraph is
serialised to `megagraph_snapshots`. Each snapshot is a JSON blob with
all nodes and edges at that moment, plus a timestamp.

This enables:

- The operator visualisation can scrub through time, showing how the
  graph grew week by week.
- If a curation mistake is made, the prior snapshot is the rollback
  point.
- The CV portfolio piece: a video or interactive showing the megagraph
  evolving from week 1 to week N.

Snapshots are also taken on demand, with a label, before any major
operator-initiated change.

For 30 users over 12 months the storage cost is trivial.

## Cross-pollination

After the first weekly curation completes, the system can surface
"nearby" interests to users — topics in the megagraph that are close
to the user's slice but not yet in it.

Mechanic:

1. For each active user, periodically (daily background job) compute
   the user's "frontier" — nodes one or two hops away from their
   engaged-with nodes that they haven't engaged with or bookmarked.
2. Rank frontier candidates by: edge weight to the user's engaged set,
   number of *other* users who have engaged with the candidate, recency.
3. Pick the top candidate (or none if scores are low).
4. Add it to the user's queue as a `suggested_interest` item.
5. On the daily page, the suggested interest can appear as one of the
   three with a "why this" line: "Other users working in adjacent
   areas have explored this. Want to add it to your interests?"

Rules:

- Cross-pollination doesn't start until after the first weekly curation
  round. Before that, the graph is too sparse for the signal to be real.
- Suggestions are anonymous and aggregated ("other users"). Even
  one is allowed per operator decision, but the phrasing should always
  be aggregate, not individual.
- Suggestions are at most one per user per week. If declined or
  dismissed, the system holds off on similar suggestions for a while.
- A user can opt out entirely if they want — a single setting.

Cross-pollination is the feature that makes the megagraph valuable
*to users*, not just to the operator. Without it, the megagraph is an
admin curiosity. With it, the megagraph quietly improves everyone's
queue.

## The user-facing skill tree view

A page where the user sees their slice of the megagraph.

What's shown:

- **The user's interest nodes**, sized or coloured by engagement level.
- **The foundation nodes the user has touched or that underpin their
  interests**, in a stable backdrop layout.
- **Edges between them**.
- **Adjacent regions**: nodes in the megagraph one or two hops from the
  user's slice, rendered greyed out. The user can click any to see
  details and add to their interests.
- **State indicators per node**: unseen, bookmarked, active,
  struggling, comfortable.

Interactions:

- Click a node: side panel shows description, subtopics, "why this
  matters" ("unlocks: X, Y, Z"), the user's history on it (problems
  attempted, papers read), and a button to engage (request problem,
  request paper, mark as bookmark, mark as comfortable).
- Click an edge: shows the relationship (prerequisite or related).
- A "what's nearby?" prompt expands the visible adjacent region.

The view is the primary way users perceive their evolving learning
landscape. It's also the discovery surface — the place where
cross-pollination suggestions live, where the user can wander and
bookmark.

The video-game feeling comes from this view. Build it as a real
visualisation, not a list with a graph icon. React Flow with Dagre
layout for v1; a more bespoke D3 version optionally later for portfolio
polish.

## The operator megagraph view

A separate admin page. Dense, less polished, functional.

What's shown:

- All nodes in the megagraph (foundations and interests).
- All edges.
- Toggle layers: user coverage, recent additions, deduplication
  decisions, pending curation proposals.
- Time scrubber: replay the graph's evolution week by week.
- Filter by domain, by user, by time range.

This is where you (the operator) run weekly curation, spot inconsistencies,
and watch the graph grow. It's also the thing worth investing in as a CV
showcase — a beautiful, animated visualisation of an evolving knowledge
graph is a striking portfolio piece. The functional version is fine for
shipping; the showcase version is a later polish.

## Data scope and assumptions

- Hard assumption: at most 30 users for the foreseeable future. No
  attempt is made to solve scale problems — the deduplication call
  considers a bounded candidate set; the megagraph query loads the
  whole graph for the operator view; snapshots are full JSON dumps.
- The interest layer is expected to grow to several hundred nodes over
  a year of active use. At that size, all operations remain
  comfortable.

## What's deliberately out of scope

- **Live deduplication confidence shown to users.** Claude's decisions
  are not user-confirmed. If Claude gets a dedup wrong, the operator
  catches it in weekly curation. Users don't need to think about it.
- **User-visible voting or signaling on nodes.** No upvotes, no "I find
  this useful," no public engagement counters. The megagraph is shaped
  by behaviour, not by deliberate user input.
- **Public sharing of the megagraph or any user's slice.** Internal to
  the product. Snapshots may be shared by the operator as portfolio
  artefacts.
- **Real-time updates of one user's view based on another's actions.**
  Updates flow through the daily/weekly cadence. No live feed.
