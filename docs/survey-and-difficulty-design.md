# Survey and Difficulty Design — Office Hours (v2)

> ⚠️ **Partially superseded (2026-06-08).** `docs/orientation-and-calibration-design.md`
> reshapes the onboarding survey and the add-interest flow and amends several
> sections here. Before building in the survey / add-interest / entry-point /
> per-problem-controls area, read that doc — it is the newer intent. Affected
> sections: **§1** (the seven-stage survey → a conversational orientation tutor +
> four signals), **§2.3** (path options → rich, detailed paths), **§3.4** (entry-
> point default → keyed on *new-to-the-user*, overridable by a go-deep signal),
> **§3.5** (per-problem controls → the easier/harder/assume-less correction loop
> still needs building). The rest of this doc (papers difficulty, tone, schema
> notes, content reuse) stands. This doc still accurately describes what is
> *currently built*; the orientation doc describes where it is going.

## About this document

This document specifies the redesigned onboarding survey, the add-interest flow (used at onboarding and during daily use), the difficulty and problem-character model, and the difficulty model for papers. It supersedes the survey design in `SPEC.md` and adds specifics that were not previously defined.

Read alongside:
- `SPEC.md` — product overview and philosophy
- `ARCHITECTURE.md` — data model and service topology
- `docs/graph-design.md` — megagraph model (deduplication, node types, edges)

The curriculum curator logic (queue intelligence — how the system sequences prerequisites and adapts over time) is specified separately in `docs/curriculum-curator-design.md`.

---

## 1. Onboarding Survey

### 1.1 Overview and principles

The survey is a guided, conversational experience. It is not a form. It should not feel like a placement test or a credential check.

Its purpose is to give the system enough signal to produce a first day's content that feels right — at the right level, on the right topics, with the right intent — without making the user fill in every field or prove what they know.

**Core constraints (from the product philosophy):**
- Never ask how long the user has to study. Never show time estimates during the survey.
- Do not gate content on foundation completion. Math prerequisites surface alongside topic content, not before it.
- The user should never feel that stating a rusty foundation locks them out of their stated interests.
- Every skip option is present. Nothing insists.

The survey has seven stages. Several are optional or abbreviated based on what the user has already said.

---

### 1.2 Stage 1 — Background page

A single page with three sections, the middle one revealed progressively as the user picks domains. Two earlier rounds of testing surfaced that a single global pick (one set of domain chips + one set of relationship cards covering everything) was too coarse — users genuinely have different relationships with different areas, and the survey was ending up producing similar-feeling queues across distinct users. This stage was redesigned to carry per-domain signal.

#### 1.2.1 Domain chips (multi-select)

Broad area chips: Physics, Mathematics, Engineering, Computation, Biology, Chemistry.

The user taps one or more. No competence level is implied. Picking a domain reveals a sub-block for that domain (see 1.2.2).

Biology and chemistry chips don't have foundation nodes in the megagraph yet, but they still feed Stage 3 suggestions (chem background tilts toward materials-physics-adjacent topics; bio background tilts toward biophysics / neuroscience interest nodes) and the add-interest dialog priors in Stage 4.

#### 1.2.2 Per-domain detail (sub-areas + relationship card)

For each picked domain, the user is offered:

**Sub-area chips** (multi-select, 4–9 options per domain). The user picks anything they've studied, encounter at work, or are curious about — the chip says "this is relevant", not any one thing about competence. Sub-areas are the primary personalisation signal: they sharpen Stage 3 suggestion ranking (Haiku rerank receives the labels verbatim) and become priors that the add-interest dialog can pull in.

The canonical sub-area lists live in [web/lib/surveyDomains.ts](../web/lib/surveyDomains.ts) as the single source of truth — that file is read by the form, the foundations stage, the Python suggestion payload builder, and the Haiku rerank prompt. The list at the time of writing:

| Domain | Sub-areas |
|---|---|
| Physics | classical mechanics · electromagnetism · quantum · relativity · thermo & stat mech · condensed matter · particle/HEP · astro & cosmology · fluids |
| Mathematics | calculus & analysis · linear algebra · ODEs & PDEs · probability & stats · discrete & algebra · geometry & topology · numerical & applied |
| Engineering | mechanical · electrical · civil · materials · chemical · software |
| Computation | algorithms & DS · machine learning · theory of computation · systems · scientific computing · data analysis |
| Biology | molecular & cell · neuroscience · physiology · ecology & evolution · genomics |
| Chemistry | organic · inorganic · physical · analytical · biochem |

**Relationship card** (single-select per domain). Four cards describing how the user relates to *that area specifically* — not a global stance:

- "I studied this and want to reconnect with it"
- "I encounter this in my work and want to go deeper"
- "I'm curious and want to understand it better"
- "I follow this field and want to engage more actively"

Optional. Different domains can have different cards (e.g. "reconnecting" with maths, "curious" about biology).

Per-domain relationship feeds into:
- Stage 2: tile label framing per-domain (1.3.4 — math tiles can read one way while physics tiles read another)
- Stage 4: dialog mirror-back tone scoped to whichever domain the resolved interest lives in
- Stage 6: mode balance pre-set, if any picked relationship strongly implies a preference

#### 1.2.3 Optional short text

No label. Placeholder: *"Anything specific about your background we should know?"*

One to two sentences, genuinely optional, no minimum. This is the escape valve for users who want to add nuance (e.g. "condensed matter physicist, been out of research for a few years — calc and EM are rusty"). Comes last, after the structured elements, so it feels like rounding out rather than being interrogated.

**Implementation notes:**
- Stored on `surveys.background_json` as `{domains: [{key, subareas, relationship}]}`. The optional short text reuses the existing `surveys.free_text_intent` column (its semantics shifted from "interest expression" in v1 to "background blurb" in v2).
- If the optional text mentions specific foundation areas as rusty, pre-mark those tiles in Stage 2 for the user to adjust. (Not yet implemented — v2.1.)
- The full text is parsed by the Haiku call in Stage 4 alongside whatever the user later types as their interests.

---

### 1.3 Stage 2 — Foundation tiles

A tappable grid of the 13 foundation nodes. The user indicates which they want to refresh. Everything else is left unmarked.

#### 1.3.1 Layout

Tiles are grouped by domain (Math section, Physics section). The domain(s) selected in Stage 1 appear first and are visually more prominent. Unselected domains are present but quieter.

#### 1.3.2 Tile content

Each tile shows:
- Topic name (e.g. "Ordinary Differential Equations")
- One-line description (e.g. "The math backbone of most physical models")
- Domain badge (math / physics)
- State indicator (see 1.3.3)

#### 1.3.3 Marking mechanism

**Two-state toggle.** Tap once: flagged for refresh (refresh icon). Tap again: back to unmarked.

"Comfortable" is not marked explicitly at this stage. The user only marks what they want to revisit. Unmarked = unspecified. Subtopic-level calibration happens in Stage 5 (concept tour), not here.

There is no "new to me" state at the tile level. Topic-level granularity is appropriate here; subtopic-level granularity is handled in Stage 5.

#### 1.3.4 Tile label framing

The label on each tile adapts to the relationship card picked in Stage 1 *for that tile's domain* — math tiles can read one way while physics tiles read another, because the relationship card is per-domain (1.2.2):
- "Reconnecting" / "Encountering at work" → *"comfortable with this?"* / *"want to refresh?"*
- "Curious" / "Follow this field" → *"know this?"* / *"new to this?"*

A db-domain has no relationship picked (the user didn't pick that domain, or picked it but skipped the card) → defaults to the refresh framing. The `applied` db-domain receives the relationship from whichever Stage 1 chip the user picked first that maps to it (engineering or computation).

#### 1.3.5 Skippability

The user can skip Stage 2 entirely. Unmarked tiles are treated as unspecified — the system calibrates from available signals and applies the entry-point default (see Section 3.4).

**Implementation notes:**

Tile marks populate `user_node_states` rows:
- Refresh-flagged → `state = 'active'`
- Unmarked → `state = 'unseen'`

`state = 'comfortable'` is not set at the tile step. That state is earned through engagement or explicitly set via concept tour responses (Stage 5) or per the user's own node panel interactions later.

---

### 1.4 Stage 3 — Interest suggestions

Based on domain tags, relationship card, optional text (Stage 1), and foundation tile marks (Stage 2), the system surfaces suggested interest nodes from the megagraph.

#### 1.4.1 Layout

A grid of suggestion tiles, visually distinct from foundation tiles (e.g. different colour, "suggested" badge, or section header: *"Based on what you've told us, here are some things you might want to explore"*).

Each tile shows:
- Interest node name
- One-line description
- A brief "why suggested" line where helpful

#### 1.4.2 Interaction

Tap to select. Selecting queues the interest for the dialog stage (Stage 4–5). Multiple interests can be selected before continuing.

#### 1.4.3 Suggestion count

Aim for 6–10 tiles. Enough for discovery; not a complete menu.

#### 1.4.4 Free text — "anything else?"

Below the suggestion tiles: a text input.
- Placeholder: *"Curious about something specific?"*
- This catches interests the suggestions didn't cover, specific concepts, or specific papers the user already has in mind.

#### 1.4.5 Continuing

When the user taps continue, the system processes all selected interests and free-text input through Stage 4 (add-interest dialog).

---

### 1.5 Stage 4 — Add-interest dialog (per interest)

For each interest queued from Stage 3, the system runs the add-interest dialog. This is the same flow used when a user adds an interest during daily use. Full specification in Section 2.

At onboarding, multiple interests may be processed in sequence or as a batch where the system detects they are related (see Section 2.2, multi-interest parsing). The user sees what has been added after each resolved interest and has an explicit option to add another or continue to Stage 5.

---

### 1.6 Stage 5 — Concept tour (per interest)

After the dialog resolves for a given interest, a concept tour runs for that interest.

#### 1.6.1 Purpose

Surface the prerequisite concepts for this specific interest. Let the user self-report their current state. This is a "lay of the land" — *"here is what will come up for this topic, so we know where to start and what to assume"* — not a placement test.

#### 1.6.2 Content

6–10 concept tiles drawn from the megagraph's prerequisite edges for the interest node just added. Tiles operate at the **subtopic level** of foundation nodes, not the topic level. (E.g. "rules for differentiation" is a subtopic of Calculus I, not a separate foundation node.)

Each tile shows:
- Concept name (e.g. "Rules for differentiation")
- One-line gloss (e.g. "Systematic shortcuts: power rule, product rule, quotient rule, chain rule")

#### 1.6.3 Three-state self-report

Three buttons per tile: **Familiar** / **Would want a refresh** / **New to me**. Tiles can also be left unclicked.

State mappings to `user_node_states`:
- Familiar → `comfortable`
- Would want a refresh → `active`
- New to me (explicit) → `unseen`
- Unclicked → `unseen` (implicit)

#### 1.6.4 Adaptive pre-marking

If the dialog or background page captured state information (e.g. "calc and EM are rusty"), relevant tiles are pre-marked accordingly. The user can adjust.

#### 1.6.5 Deduplication across interests

If multiple interests share prerequisite nodes, concept tour tiles are deduplicated across sequential tours. A tile already addressed in an earlier interest's tour is not re-shown in subsequent tours unless the state was not captured.

#### 1.6.6 Skippability

The tour is skippable in full. A visible skip option is always present. No nag.

#### 1.6.7 "New to me on everything"

If the user marks every tile as "new to me" or leaves all unclicked, the system proceeds silently. The entry-point default (Section 3.4) handles this case. No special message.

**Implementation notes:**

Subtopic tagging on problems is load-bearing for the concept tour to function correctly. See Section 3.7.

The subtopics shown in concept tours are the same subtopics accessible via the node panel in the skill tree view. Shared data source — the subtopics are defined on the node, surfaced in both places.

Tile selection (`_concept_tour` in `api/routes/add_interest.py`) draws from the resolved node's `prerequisite` edges, foundation nodes first, and takes tiles **round-robin** across those prerequisites so one foundation's long subtopic list can't crowd out the others (Phase 10.5-rev Step 4). Interest-kind prerequisites contribute only as a fallback when foundations don't yield a worthwhile tour.

Cross-tour deduplication (§1.6.5) is **node-scoped and addressed-only**: a tile is suppressed in a later tour only when an exact `(node_id, subtopic_key)` match was actually *answered* in an earlier tour. Tiles the user left unanswered reappear — "unless the state was not captured" is load-bearing. Keying on the subtopic name alone, or marking every shown tile seen, over-fires and silently skips whole sub-tours (the Step 4 s15 bug).

---

### 1.7 Stage 6 — Mode balance (optional)

A single slider: paper-heavy ↔ problem-heavy. Default 50/50.

If the add-interest dialog or relationship card strongly implied a mode preference, the slider is pre-set accordingly with a brief note: *"I've set this based on what you said — adjust if you want."*

Examples of strong mode signals:
- "I want to follow the LIGO papers" → papers-heavy pre-set
- "I want pure math problems, no physics" → problems-heavy pre-set

"I want to reconnect with solid state physics" does not strongly imply a mode — default 50/50.

The user can adjust or skip with "use the default."

**Post-onboarding:** Mode balance lives on the profile page. It can be changed at any time without re-doing the survey.

---

### 1.8 Stage 7 — Confirmation

The user sees their initial megagraph slice rendered: their interest nodes, the foundation nodes underpinning them, edges between them, and greyed-out adjacent regions.

#### 1.8.1 Purpose

Make the system feel responsive and real — not a black box. The user should see that what they said produced something concrete before they enter daily use.

#### 1.8.2 Node interaction

Tapping any node opens a panel.

**Interest nodes:**
- Description, subtopics, "why this matters"
- Two actions:
  - **Delete** — removes from the user's interests (`user_interests` row removed; the node itself stays in the megagraph and remains available to other users)
  - **Edit** — opens a text field: *"What's off?"* — triggers re-run of the add-interest dialog for this specific node. If the user's description concerns the node's accuracy rather than their own relationship to it (e.g. "the description of superconductors is wrong"), the system flags it for operator curation rather than silently applying changes.

**Foundation nodes:**
- Description, subtopics, "why it's in your graph"
- No delete or edit action. Foundation nodes are operator-curated. The user's relationship to foundation nodes is adjusted through the tile step and concept tours, not the confirmation moment.

#### 1.8.3 Exiting the survey

A *"your queue is ready"* line leads the user to the first daily view.

---

## 2. The Add-Interest Flow

This flow is used both at onboarding (Stage 4) and when a user adds an interest during daily use. The mechanic is the same in both contexts.

**Presentation differs by context:**
- Onboarding: full page, sequential
- Daily use (from the "Curious about something specific?" input or from the skill tree): panel or modal

---

### 2.1 Step 1 — Free-form input

The user types what they want. No constraints on form or length — one word, a sentence, a paragraph.

---

### 2.2 Step 2 — Haiku parse

A Haiku call extracts three signals:

#### 2.2.1 Topic(s)

Deduplicate against the existing megagraph per the logic in `graph-design.md`. If the statement contains multiple interests, Claude with the megagraph as reference proposes how to split them.

**Multi-interest splitting rule:**
Pass the user's statement and the relevant megagraph slice to Claude. Prompt: *"How many distinct interests does this statement contain, at the granularity the existing graph uses? For each, is it a match to an existing node, related-but-distinct, or genuinely new?"*

- The system creates or links nodes accordingly.
- The split is per-user and invisible — no separate split-confirmation UI.
- The proposed split appears in the mirror-back (Step 3) for the user to adjust if wrong.
- Default: coarse-grained when the graph is sparse (early product life). Coarse-grained splits are easier to refine via weekly curation than over-fine splits.
- Splitting decisions are included in the weekly curation report for operator review.

#### 2.2.2 Specificity

Is the stated intent committed to a path, or broad enough to need clarification?

- **Specific**: "I want to follow GW physics — LIGO, the detection papers, where the field's going"
- **Ambiguous**: "I want to learn semiconductors"

#### 2.2.3 Implicit intent dial

Does the language suggest teach, refresh, or extend (consolidate)?
- "I want my ODEs back" → refresh
- "I want to learn semiconductors" → teach
- "I want harder problems on Kalman filters" → extend

---

### 2.3 Step 3 — Branch on specificity

#### Specific intent

System mirrors back in natural language. Followed by one optional prompt: *"Want to tell me more about what draws you to this?"*

This beat is **optional and skippable**. It is not mandatory. Its purpose is to give the user a moment to articulate their goal in their own words, and to give the generator richer texture. If the user skips it, the system proceeds with what it has.

#### Ambiguous intent

System mirrors back and surfaces the paths it sees, conversationally. Example for "I want to learn semiconductors":

> *"That covers a few different angles — which sounds closest? (a) How transistors and circuits actually work, (b) The deeper physics of why semiconductors behave the way they do, (c) Applications like LEDs, solar cells, and lasers, (d) Following current research in the field. Or something else — tell me what you're after."*

Free-text response and tap-to-select both welcome. Multi-select is allowed.

The system does not enumerate all possible paths — it surfaces the ones it can infer from the available megagraph, typically 3–5 options, always with an "or something else" escape.

---

### 2.4 Step 4 — Resolve and preview

System mirrors the resolved intent and names a concrete starter item:

> *"Got it — GW physics, research-following style. Your first item will be: [entry-point paper title]. It'll appear in your queue."*

The preview is one specific item, not a description of a category. The user should feel: *"yes, that's exactly what I meant."*

---

### 2.5 Step 5 — Concept tour

Per the specification in Section 1.6.

At onboarding: runs for each interest in sequence, with deduplication.
Post-onboarding: runs as a panel/modal after the dialog resolves, lighter framing, same mechanic.

---

### 2.6 Data stored

For each interest added, a `user_interests` row is created or updated:

| Field | Value |
|---|---|
| `node_id` | The matched or newly created node |
| `intent_context` | Soft text/tags capturing the resolved path and intent. Free text generated from the dialog — **not a hardcoded enum**. Examples: "devices-and-circuits angle, teach intent"; "research-following, papers-heavy". This field is read by the problem generator and the queue intelligence logic. |
| `added_via` | `survey` / `explicit_request` / `cross_pollination` |

`intent_context` is the primary mechanism by which path information is captured per-user without subdividing megagraph nodes. It must be populated for every interest added. It must be passed to the problem generator when generating content for that interest.

---

### 2.7 The "Curious about something specific?" input box

A persistent text input on the daily tab, below the three content cards.
- Placeholder: *"Curious about something specific?"*
- Always visible, not prominent

This input handles three cases:

#### Case 1 — New topic

The user requests something not currently in their interests. System surfaces a branch:

> *"[Topic] isn't in your interests yet — want to add it, or just get one item for now?"*

- **"Add it"** → full add-interest flow (dialog + concept tour), presented as a panel/modal.
- **"Just this once"** → queues a single entry-point item on the topic without adding a permanent interest. No dialog, no concept tour.

#### Case 2 — Existing topic, one-off

The user requests something on a topic already in their interests. System queues the item directly. No dialog triggered.

#### Case 3 — Concept or subtopic request

The user asks about something at the sub-node level (e.g. "I've forgotten what power means in physics"). System detects this is a concept-level request, not a new interest. Response: a brief orienting explanation and one focused problem. No new node created. No add-interest flow triggered. Queries the problem pool first (subtopic tag match) before generating new content.

---

## 3. Difficulty and Problem Character

### 3.1 The three dials

Every problem has three independent properties. They are not facets of one thing — they are genuinely separate and must be designed and controlled separately.

#### Difficulty

How hard the actual reasoning is, once the user has the concepts the problem relies on. Ranges from accessible to demanding.

**Default:** moderate — real intellectual engagement, but tractable for someone who has been given the relevant concepts.

**User control:** per-problem easier/harder request. Generates a sibling problem at a different difficulty level. The original problem stays in the pool.

#### Assumed background

How much the problem takes for granted versus builds up. **This is the most important dial and the most frequently miscalibrated one.**

The rule: a problem may assume only what the system has confirmed the user has. If a concept is needed and has not been confirmed, the problem must introduce or recall it rather than presuppose it. Specifically:
- Concepts needed to work through the problem are introduced before being used, not presupposed.
- Technical terms are defined when first used, not referenced in passing as though the user certainly knows them.
- Prior results are cited and briefly explained, not smuggled in.
- The problem does not assume fluency with notation the user has not been given.

The assumed background scales dynamically: if the user has confirmed comfort with X (via concept tour, tile mark, or engagement behaviour), X can be assumed. If not, it must be built up.

**User control:** "explain more / assume less" request per-problem, or persistent feedback via the profile page.

#### Intent

What the problem is trying to do. Three valid values:

**Teach** — the user hasn't seen this before, or it has been long enough to feel new. The problem introduces the concept, builds up the apparatus, and guides toward a result that illuminates something. Getting through it should feel like: *"I now understand [concept] better."*

**Refresh** — the user half-remembers this. The problem recalls the idea and re-establishes intuition. Does not demand a cold-start derivation. Assumes the user has some residual context.

**Consolidate** — the user has marked this topic as comfortable. The problem confirms it is still solid. Assumes the topic's concepts. Surfaces infrequently (spaced practice). This is the only intent mode where the problem can assume the full topic apparatus — it is appropriate because the user has explicitly stated comfort, not because the system decided to test them.

**What intent is almost never right:** pure test mode — demanding mastery the user never claimed to have, referencing apparatus that has not been built up, making the user feel inadequate.

---

### 3.2 What a good problem does

- Introduces any concept or term it needs before using it.
- Gives a context paragraph that genuinely motivates the problem — not historical decoration, but connective tissue linking it to the user's interests and recent work.
- Builds toward a result that illuminates something: not algebra for its own sake.
- Uses notation consistently and explains anything non-standard.
- Leaves the user feeling: *"I worked through that and now I understand [concept] better."*

### 3.3 What a good problem does not do

- Reference a model, notation, or prior result without explaining what it is.
- Ask the user to "show that…" something requiring unexplained machinery.
- Assume fluency with a named model, standard technique, or famous result as though the user certainly has it.
- Introduce three unexplained prerequisites in the setup paragraph.
- Feel like an examiner checking whether the user already knows the material.

**The contrast case:** a problem that opens by asserting the RCSJ model, the Josephson relations, and the Stewart-McCumber parameter — all without introduction — is wrong on all three dials simultaneously. High assumed background, test intent, high difficulty. This is appropriate for a graduate course problem set where students have built up the apparatus over weeks. It is never appropriate for a user meeting the topic for the first time or returning to it after years away.

---

### 3.4 Entry-point default

Every new interest enters at its conceptual entrance. The first problem on a new interest answers something like *"what is this thing and why does it behave this way?"* before asking the user to calculate or derive.

The entry-point default applies regardless of the user's stated background. A physicist with a PhD who adds "superconductors" as a new interest still gets a conceptual entry-point problem first — the background affects how fast to progress past it, not whether to start there.

**What the entry-point problem is not:** it is not a beginner's explainer or a simplified toy version. It is the conceptual entrance to the topic — the question that establishes what the thing is and why it matters, before the apparatus is built.

---

### 3.5 User controls on the dials

| Control | Dial affected | Mechanism | Where |
|---|---|---|---|
| Easier / Harder | Difficulty | Generates a sibling problem; original stays in pool | Per-problem, before starting |
| Explain more / Assume less | Assumed background | Adjusts generator instructions for this problem; persistent feedback adjusts across all problems for this topic | Per-problem, or profile page |
| Not ready yet — come back later | All three | Conditional deferral: re-queues this problem; triggers accelerated prerequisite surfacing; problem returns when prerequisites have been addressed | Per-problem, before starting |
| Profile page feedback ("my problems are too hard", "problems assume things I haven't seen") | Difficulty / Assumed background | Adjusts generator instructions across the relevant topics | Profile page |

The "Not ready yet" action is distinct from:
- **Skip** — implies the user does not want to see this content (negative preference signal)
- **Save for later** — indefinite deferral with no conditional logic
- **Mark as refreshed** — implies the user looked at it and feels fine

"Not ready yet" means: *"I want this, but I need the prerequisites first."* The system treats it as a signal to accelerate the relevant prerequisite content and re-queue this problem once that content has been engaged with.

---

### 3.6 The practical generation test

Before a problem is generated, it should pass this check:

> *Could a user who has only the background the system has confirmed work through this problem?*

If the answer is no — if the problem assumes something the system has not confirmed the user has — the assumed background dial is set wrong. Revise until the answer is yes.

This check applies at generation time and should be enforced in the generation prompt. The `intent_context` field on `user_interests` and the `user_node_states` for the relevant foundation and interest nodes are the inputs to this check.

---

### 3.7 Content reuse and subtopic tagging

Problems exist in a shared pool. They are generated to build the pool, not freshly generated for each user request. Foundation node problems are pooled and shared across all users. Interest node problems have smaller pools (more niche topics) but the same principle applies.

**Subtopic tags are load-bearing.** When any surface requests a refresher on a specific concept — the input box, the node panel subtopic refresh action, the concept tour, a proactively-timed prerequisite — the system queries the pool:

```
WHERE topic_node_id = [node] AND tags @> ARRAY['[subtopic]']
```

If a suitable problem exists, it is drawn from the pool. New generation is triggered only when the pool has no suitable match.

**Required tagging on every generated problem:**
- `topic_node_id` — the primary node the problem belongs to
- `tags` (text array) — must include both the primary topic and all subtopics the problem meaningfully addresses

Example: a problem about power in a physics context should have `tags = ['classical_mechanics', 'power', 'energy_transfer', 'work']`. A problem that only tags `['classical_mechanics']` will not surface when the user requests a power refresher specifically.

Subtopic tag generation must be included in the problem generation prompt. This is not optional metadata.

---

## 4. Difficulty for Papers

Papers do not follow the same difficulty model as problems. You cannot generate an easier or harder version of a paper — the paper is what it is. The levers are in how the system selects papers, frames them, and structures engagement around them.

### 4.1 Paper selection

The primary lever. The range spans from accessible review articles and pedagogical papers to recent, technically dense research papers.

The system matches paper accessibility to the user's current depth within the interest topic:
- New to a topic → accessible review article or classic introductory paper
- Several weeks into a topic with active engagement → recent research papers

The system tracks depth per interest node the same way it tracks problem depth.

### 4.2 Orienting concepts depth

The preparation provided before the user reads. Adjusts based on paper density and user depth:
- Denser paper or newer user on the topic → more extensive orienting concepts, more "refresh this first?" links
- Familiar terrain → lighter framing, let the paper speak

### 4.3 Engagement question depth

Questions range from comprehension-focused to analytical and connective. Pitched based on the user's depth in the topic and the paper's technical demands:
- Comprehension: *"What is the paper's central claim?"*
- Analytical: *"What are the limitations of the approach?"*
- Connective: *"How does this relate to your other interests?"*

### 4.4 User feedback for papers

*"This was too technical for me"* or *"I want something more challenging."* These adjust future paper selection and orienting-concept depth for that topic. There is no per-paper easier/harder mechanic — that belongs to problems only.

### 4.5 What difficulty does not mean for papers

Papers do not have a difficulty slider. The assumed background dial for problems (which can be adjusted per-problem) does not apply to papers in the same way. The paper's content is fixed; the system can only adjust the framing around it and the selection of which paper to show.

---

## 5. Tone

The survey — and the product throughout — speaks like a knowledgeable peer helping the user set something up. Not a teacher assessing them. Not a system collecting data points.

### 5.1 Four defining qualities

**Conversational.** Natural language throughout. Short sentences, active voice. *"What are you curious about?"* not *"Select your areas of interest."* *"Got it"* not *"Your preferences have been recorded."*

**Peer to peer.** The system treats the user as a competent adult — an intellectual equal who wants help with something specific, not a student who needs to prove themselves first. It does not ask them to demonstrate what they know. It does not gate or condescend. It trusts that they know their own mind.

**Calibrated.** The system responds to what *this specific user* said, not to a generic user. If the user mentioned rusty foundations, the confirmation acknowledges that. If the user said research-following, the entry point reflects it. The user should never feel they could have typed anything and received the same response.

**Knows what you want.** When the system mirrors back intent or confirms a path, it should feel like *"yes, that's exactly what I meant."* It uses the user's language where possible. It shows it heard them — not with a data summary, but with a response that could only have come from what they said.

### 5.2 What it does not sound like

A placement test. A university intake form. A chatbot with canned responses. Anything ending in *"Your submission has been received."*

### 5.3 Scope

This tone applies throughout the product, not just the survey. The "why this" lines on daily cards, context paragraphs in problems, feedback after submissions, orienting concepts before papers — all maintain this register. The survey establishes the voice; everything after it maintains it.

---

## 6. Profile page

The profile page is the home for user-adjustable preferences and feedback. It does not need to be fully implemented in the first release, but the following items belong there:

- Mode balance slider (paper-heavy ↔ problem-heavy)
- Feedback surface for high-level adjustments: *"My problems are too hard"*, *"Problems assume things I haven't seen"*, *"I want more papers"*, *"I want harder problems"*. These map to the difficulty and assumed-background dials and adjust generator instructions for the relevant topics.
- Interest management: view current interests, remove, adjust
- Foundation node states: view current states
- Activity summary (future)

Feedback submitted via the profile page adjusts the system's generator instructions for the relevant interests and is noted in `user_node_states` or a future `user_preferences` table. The change is invisible to the user in its mechanics — they see the results in their queue, not the machinery.

---

## 7. Skill tree — node panel additions

The skill tree node panel (opened by tapping any node in the skill tree view) should be extended to show subtopics for foundation nodes, with a per-subtopic refresh action.

For each subtopic listed in a foundation node's panel:
- Show the subtopic name and one-line description
- Show the current state (familiar / refresh / unseen), if known
- Offer a *"request a refresher"* action

Tapping *"request a refresher"* on a subtopic triggers the same concept-level response as Case 3 in Section 2.7: queries the problem pool for a subtopic-tagged problem and queues it. No new node created.

This makes specific concept gaps addressable directly from the skill tree, without requiring the user to know to type them into the input box.

---

## 8. Schema changes and additions

The following changes to the existing schema are required by this design. All other tables are unchanged.

### 8.1 `surveys` (CHANGED)

Three columns added (migration `20250019_phase10_survey_v2_shape.sql`) to support the route-per-stage shell's progressive draft and the per-domain Stage 1 redesign:

| Field | Type | Notes |
|---|---|---|
| `background_json` | JSONB | Stage 1 per-domain selections: `{domains: [{key, subareas, relationship}]}`. Default `'{}'::jsonb`. Read by the foundations stage (tile labels, foregrounding) and by the Python `/survey/suggest-interests` endpoint (Haiku rerank prompt). |
| `completed_stages` | TEXT[] | Ordered list of survey stages the user has finished. Drives the route-per-stage gate so reload mid-survey resumes correctly. |
| `pending_interests_json` | JSONB | Stage 3 selections + free text handed to the Stage 4+5 stub (Step 2c) / dialog (Step 2d) at server time. Cleared once `user_interests` rows are written. |

The existing `comfort_responses_json` field will now be populated from concept tour responses (previously empty) — wired by Step 2d when the concept tour UI lands. The existing `free_text_intent` column's semantics shifted in v2 from "interest expression" (v1) to "Stage 1 optional background blurb" (v2).

### 8.2 `user_interests` (CHANGED)

Add one field:

| Field | Type | Notes |
|---|---|---|
| `intent_context` | TEXT | Soft text capturing resolved path and intent from the add-interest dialog. Not a hardcoded enum. Required — must be populated for every interest added. Read by the problem generator and queue intelligence. |

### 8.3 `user_node_states` (no structural change)

No new fields. However, concept tours now actively populate this table during onboarding — previously it was populated only through engagement behaviour. Ensure the concept tour Step 5 writes `user_node_states` rows for every tile the user responds to.

### 8.4 `problems` (CHANGED — operational requirement)

No new fields. The existing `tags` text array is already present but has been treated as optional metadata. It must now be treated as load-bearing.

**Requirement:** every generated problem must include both topic-level and subtopic-level tags. The generation prompt must explicitly request these tags as part of the problem output. Problems without subtopic tags will not surface correctly for concept-level refresher requests.

### 8.5 `queue_items` (CHANGED)

Add one state value to the existing `state` enum:

| New value | Meaning |
|---|---|
| `deferred` | The user tapped "not ready yet — come back later." The item is conditionally re-queued. It returns to `pending` when the queue intelligence determines the relevant prerequisites have been addressed. |

`deferred` is distinct from `skipped` (user does not want this content) and `dismissed` (user has rejected it). A deferred item is expected to return.

### 8.6 `attempts` (CHANGED)

Add one field:

| Field | Type | Notes |
|---|---|---|
| `requested_assume_less` | BOOLEAN | True if the user requested "explain more / assume less" for this problem. Signals the generator to produce a sibling with lower assumed background. Analogous to `requested_easier` / `requested_harder`. |

---

## 9. What this document does not cover

The following are explicitly out of scope for this document and are specified (or to be specified) elsewhere:

- **Curriculum curator / queue intelligence** — how the system sequences prerequisites, proactively times refreshers, and adapts queue composition based on engagement signals. Specified in `docs/curriculum-curator-design.md`.
- **Weekly operator curation** — megagraph maintenance, merge/split/rename proposals. Specified in `docs/graph-design.md`.
- **Cross-pollination** — surfacing adjacent interests from the megagraph. Specified in `docs/graph-design.md`. Note: cross-pollination suggestions surface as one of the three daily cards (not as a separate box below), with a "why this" line and the option to add to interests.
- **Problem and paper engagement flows** — hint panels, solution submission, dialogic feedback, paper Q&A. Specified in `SPEC.md`.
- **Notebook** — specified in `SPEC.md`.
- **Full skill tree view design** — React Flow implementation, layout, state indicators. Specified in `SPEC.md` and `docs/graph-design.md`. This document adds only the subtopic panel extension (Section 7).
