# SPEC.md — Personalized Science Tutor (v2)

> A personal science tutor for working professionals. You tell it what you
> want to understand — could be something specific like FETs or
> gravitational waves, could be broader like "I want my calculus back" —
> and it builds you a path. Each day it gives you one thing: a paper to
> work through, or a problem to solve with pen and paper. The papers are
> recent and chosen for you; the problems sharpen the math you need to
> actually understand the papers. Hints help when you're stuck but never
> solve it for you. Everything you do gets written up into your own LaTeX
> notebook, so over time you build a real record of what you've learned.

> Quietly, as you and your friends use it, the topics you each explore
> grow into a shared map — a knowledge graph of what working scientists
> are actually curious about, and a discovery surface for what's nearby.

## About this document

This is the second version. The first (in `docs/archive/SPEC-v1.md`)
described a curriculum-walk product organised around a static skill tree
and daily problems. Real use revealed it felt like undergraduate
homework — too prescriptive, generic, disconnected from the specific
things working scientists actually want to understand.

This version reframes around user-driven interests, a fluid queue of
content, paper engagement as a first-class mode, an evolving notebook,
and a shared knowledge graph that grows with use (the "megagraph"). See
`docs/graph-design.md` for the full graph model and `docs/personas.md`
for persona writeups that ground the design.

## Out of scope

- Public sign-ups, marketing, payments
- Multi-tenant or team features
- Mobile native apps (mobile *web* is in scope)
- Streaks, badges, leaderboards, social features
- Content moderation beyond standard auth — small trusted user base
- Solving for scale — hard cap of 30 users for the foreseeable future

## Users

Self-selected friends of the operator. Working scientists or technical
professionals who studied math/physics/related fields years ago and want
to stay sharp and stay current. Authenticated by email magic link. No
sensitive data is stored.

Three primary personas in `docs/personas.md`.

## Core philosophy

Treat these as constraints on feature decisions, not slogans.

- **No guilt, no streaks.** The product is here when you want it.
- **Working professionals are competent.** Don't gate, don't condescend.
- **Pen and paper is the medium.** Hand-writing solutions and submitting
  is a feature, not a friction.
- **Hints help; they don't solve.** Progressive disclosure; no final
  answer or full solution path.
- **Feedback is dialogic.** Claude responds like a thoughtful colleague,
  not a teacher with a rubric.
- **The notebook is the artefact.** Everything done accumulates into
  the user's LaTeX-rendered record.
- **The system curates; the user trusts.** Affordances exist for
  explicit direction; they're not the default surface.
- **Time is not a commitment.** Users are never asked to budget time.
- **The graph is shared and grows with use.** Users' interests merge
  into a megagraph that surfaces nearby topics across the user base.
  This is invisible plumbing as far as daily use; it's a defining
  feature of the product as a whole.

## Core concepts

### The queue

Each user has an active queue of content items — problems, paper
engagements, refreshers, concept reviews, and suggested interests (from
cross-pollination). The queue isn't visible in full; it drives the daily
surface. Items are added by the system based on user interests, recent
work, adjacent topics, and the megagraph. Plans (in v1's sense) don't
exist; the queue replaces them.

### The graph (foundations + interests)

The product's knowledge graph has two layers:

- **Foundation nodes** are operator-curated, stable, ~13 in the initial
  seed (calculus, ODEs, linear algebra, classical mechanics, etc.).
  Shared across all users.
- **Interest nodes** are user-added, organic, accumulate over time.
  They cover what working scientists actually want to learn (FETs,
  gravitational waves, Kalman filters, etc.). Also shared across users
  via deduplication.

Together they form the megagraph: a single shared structure that grows
with use. See `docs/graph-design.md` for the full model.

### The skill tree view

A page where the user sees their slice of the megagraph: their interest
nodes, the foundation nodes they've touched or that underpin their
interests, edges between them, and a greyed-out backdrop showing
adjacent regions of the megagraph they haven't explored.

This is the discovery surface and the visual identity of the product.
Users can click any node — including greyed adjacent ones — to see
details and engage with it. State indicators (unseen, bookmarked, active,
struggling, comfortable) show progress.

### The notebook

The long-form record of a user's work. Every problem attempt and paper
engagement produces a notebook entry, rendered as Markdown + LaTeX,
preserved indefinitely. Browsable, searchable, exportable. See "Notebook
details" below.

### Refreshers

Spaced resurfacing of prior content. After enough time has elapsed
since a problem, paper, or derivation, the system may surface a short
refresher on it as one of the day's options.

### Save for later

Users can bookmark anything — a topic seen in a problem's context, a
paper mentioned in another paper's engagement, a subtopic from the skill
tree, an adjacent megagraph node. Bookmarks are browsable; bookmarks can
be promoted to interests when the user is ready.

## Onboarding

A short, mixed-mode survey:

1. **Free-text intent.** "In a few sentences, what do you wish you
   understood better? Anything from a broad topic to a specific paper or
   concept is fine." The primary signal. The system parses this into
   one or more initial interest nodes, with deduplication against the
   megagraph.
2. **Skill tree exploration.** A view of the foundations layer plus
   neighbouring interest nodes (from the megagraph) where users click
   around and mark nodes as "interested," "comfortable," or "want to
   refresh." Partial exploration is fine.
3. **Comfort calibration.** A handful of concept-recognition questions
   covering common foundations (basic calculus, linear algebra,
   mechanics). Used to seed the system's initial sense of where to pitch
   problems.
4. **Mode balance.** A single slider: paper-heavy to problem-heavy.
   Changeable any time. Default 50/50.

Survey completion produces:

- The user's initial interest nodes (linked into the megagraph)
- The user's first queue
- A first day's surfaced items

## Daily experience

When a user opens the app, they see three surfaced items from their
queue, varied in length and mode when the queue permits. Each item
shows:

- Title and short description
- The relevant topic(s) it's drawn from — the interest and/or foundation
  node(s) the item belongs to, shown as a label/chip so the user can see at a
  glance what area each card covers
- Mode badge (problem / paper / concept / suggested interest). Items that
  revisit material the user has already worked on additionally carry a
  "refresher" badge — a framing flag (`via_refresher`) on a concrete item,
  not a separate kind (see Phase 10.5-rev Step 2)
- Estimated time as a coarse range
- Brief "why this" — connection to user's interests, recent work, or the
  megagraph

A **reroll** button surfaces a different selection. No limit. Rerolls
are an implicit signal — repeated rerolls of a mode or topic adjust
future queue composition.

Users can also explicitly request:

- "Give me a problem on [topic]"
- "Find me a paper on [topic]"
- "Refresher on [topic]"
- "Add [topic] to my interests" — runs the dedup/extension flow on the
  megagraph

## Adding an interest

When a user adds an interest (at onboarding or later), the system:

1. Sends a Haiku call to deduplicate against existing megagraph nodes.
2. If the interest matches an existing node, links the user to it.
3. If it's new, creates a node and generates its description, subtopics,
   and prerequisite edges via a Sonnet call.
4. Adds relevant content (refreshers on prerequisites the user hasn't
   covered, a starter problem or paper on the new interest) to the queue.

The user sees a brief confirmation; the heavy lifting happens
asynchronously where possible. See `docs/graph-design.md` for the full
flow.

## Content modes

### Problems

The user is shown:

- **Problem statement** rendered with LaTeX.
- **Context paragraph(s)** providing motivation. Where relevant, the
  context names adjacent topics, papers, or historical episodes — each
  bookmarkable. Context is connective tissue, not historical wrapping.
- **Hint panel**, collapsed by default. Pre-generated; progressively
  disclosed; never solves.
- **Difficulty controls.** Request "easier version" or "harder version"
  before starting. Generates a sibling problem; the original remains in
  the pool.

User writes by hand, photographs, uploads. System parses to
Markdown + LaTeX. User reviews and edits the parse. System grades with
dialogic feedback. Hints used recorded. The exchange saved to the
notebook.

A "mark as refreshed, skip" option exists for cases where the user looks
and feels they have it. Used as adaptation signal; no drilling.

### Papers

The user is shown:

- **Why this paper.** One paragraph connecting it to interests or recent
  work.
- **Orienting concepts.** 2–4 key terms with one-sentence glosses.
  Concepts the user hasn't seen are flagged with an optional "refresh
  this first?" link.
- **Link to the paper** (linked out; not rendered in-app).
- **Engagement questions.** 3–5 questions of mixed type (comprehension,
  critical, connective, open), each calling for a 2–4 sentence response.
  Pre-generated when the paper enters the queue.

User reads externally, returns to answer. Multi-session supported (one
in-progress paper at a time per user). Claude responds to each answer
conversationally. Free-form Q&A after the questions, 2–3 turns. Saved
to the notebook.

### Paper discovery

Papers enter the queue from three sources:

1. **System-suggested.** Claude proposes papers based on the user's
   interests and recent work. Primary source.
2. **User-provided.** Paste an arXiv URL, DOI, or title. System ingests.
3. **Adjacent surfacing.** Papers mentioned in other papers'
   engagements, or referenced in problem context, become bookmarks or
   suggestions.

For v2, Claude proposes from its training knowledge. Live arXiv search
is deferred.

## Adaptation

The queue evolves based on what the user does:

- Struggle (hints used, problems wrong, slow paper engagement) triggers
  reinforcement.
- Ease triggers acceleration to more advanced or adjacent topics.
- Reroll patterns shift mode balance softly.
- New interests trigger queue reassessment.
- Refreshers are scheduled by time-since-engagement.
- Megagraph adjacency triggers cross-pollination suggestions (after
  the first weekly curation round; see `docs/graph-design.md`).

Adaptation is invisible to the user.

## Cross-pollination

After the first weekly curation round, the system may surface
"suggested interest" items — nodes in the megagraph that are near the
user's slice but not yet in it. Surfaced anonymously and in aggregate
("three other users in adjacent areas explored this"), at most once per
week per user. See `docs/graph-design.md` for the surfacing rules.

## Weekly curation (operator)

A weekly background job generates a curation report on the megagraph:
proposed merges, splits, renames, promotions, demotions, new edges, and
deprecations. Operator reviews and approves in an admin UI. Approved
changes are applied; a megagraph snapshot is taken. Expected operator
time per round: 15–30 minutes.

## Notebook details

Every problem and paper engagement produces a notebook entry. Entries
contain:

- Title, date, topic tags (node slugs from the graph)
- For problems: statement, context, hints used, parsed solution,
  feedback, follow-up
- For papers: title and link, why-this, orienting concepts, user's
  answers and Claude's responses, any Q&A

Notebook is browsable by date and topic, full-text searchable, and
(later) exportable as LaTeX or PDF.

## Non-functional requirements

- **Mobile-first** for daily-three view, problem submission, notebook
  reading. Desktop optimised for survey, paper engagement, skill tree,
  admin.
- **Cost monitoring.** Every LLM call logged with tokens and cost.
  Admin dashboard shows daily/weekly/monthly spend.
- **Trust model.** Small known user base.
- **Latency.** Daily surface loads instantly. Pooled content draws are
  instant. Bespoke generation (new interest, paper engagement) is a few
  seconds with a loading state.
- **No scale engineering.** 30 users is the hard cap.

## Definition of done (v2)

- New user signs up, completes the survey, sees a daily three of varied
  content matching their interests.
- User can engage with a problem (statement, hints, photograph,
  feedback, notebook entry).
- User can engage with a paper (why-this, concepts, link, questions,
  dialogic feedback, Q&A, notebook entry).
- User can request specific topics or content; queue responds.
- User can add a new interest in free text; system deduplicates against
  the megagraph and integrates appropriately.
- User can browse their skill tree view, see their slice, see adjacent
  greyed regions, click to explore.
- Cross-pollination surfaces nearby interests (after first weekly
  curation).
- User can save items for later.
- Refreshers surface appropriately.
- Operator can run weekly curation: review proposals, approve, see
  snapshots.
- Operator can see spend and pool/megagraph health.

## Deferred (v2.1+)

- Live arXiv / Semantic Scholar paper search and ingestion
- Calendar tracker / engagement history view in notebook
- Return-after-absence prompts
- BYO Claude API key for users on paid plans
- Per-user time-estimate calibration
- Notebook export as LaTeX or PDF
- Hand-authored problem entries (operator curation surface for problems)
- Per-user difficulty calibration beyond per-problem dial
- Notebook annotations outside of engagements
- Saved partial problem attempts
- Bookmark promotion workflows
- Bespoke D3 megagraph visualisation for portfolio (initial version is
  React Flow + Dagre)
