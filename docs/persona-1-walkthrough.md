# Persona 1 — Four-Week Walkthrough

## About this document

This is an illustrative walkthrough of the Office Hours experience for Persona 1 over their first four weeks. It is a worked example, not a test specification. Its purpose is to show how the survey design, add-interest flow, difficulty model, and curriculum curator are expected to feel in practice when they are working correctly.

Read alongside:
- `docs/survey-and-difficulty-design.md` — the survey and problem character specification
- `docs/curriculum-curator-design.md` — the queue intelligence specification

**Persona 1:** A recovering condensed-matter scientist. *"I want to relearn solid-state physics, my calc and EM are rusty, interested in semiconductors and superconductors."* Mixed problems and papers. Has a real topic goal plus acknowledged rusty foundations. This is the hardest persona to serve well — a real goal, specific interests, and gaps they are aware of.

---

## Day 0 — The survey

### Background page

A clean page loads. Domain tag chips along the top. Persona 1 taps **Physics** and **Mathematics**. The relationship cards appear:

- *"I studied this area and want to reconnect with it"* — this one
- *"I encounter this in my work and want to go deeper"* — less so

They tap **reconnecting**. The optional text field sits underneath. They type:

> *"Condensed matter physicist, been out of active research for a few years. Main interest is solid state physics — semiconductors and superconductors specifically. Calculus and EM are pretty rusty."*

---

### Foundation tiles

Physics section loads first, slightly more prominent. The label on each tile reflects their relationship card: *"comfortable with this?"* / *"want to refresh?"*

They work through:

| Foundation node | Mark |
|---|---|
| Calculus I / II | Comfortable (unmarked) |
| Multivariable Calculus | **Refresh** — surface integrals and grad/div/curl are fuzzy |
| Linear Algebra | Comfortable |
| ODEs | **Refresh** — already said so in their text |
| Probability / Statistics | Comfortable |
| Classical Mechanics | Comfortable |
| Waves & Oscillations | Comfortable |
| EM I | **Refresh** — Maxwell's equations need a revisit |
| Thermodynamics | Comfortable |
| Statistical Mechanics | **Refresh** — been a while; will come up in solid state |
| QM I | Comfortable |

They leave the rest unmarked and continue.

---

### Interest suggestions

The system surfaces a set of tiles: *"Based on what you've told us, here are some things you might want to explore."*

Suggestions shown:
- Solid State Physics
- Semiconductor Devices
- Superconductivity
- Crystal Lattices and Phonons
- Band Theory
- Condensed Matter: Phase Transitions

They tap **Solid State Physics**, **Semiconductor Devices**, and **Superconductivity**. Leave the others. The *"anything else?"* box: they type *"Topological insulators — I want to at least understand what people mean when they talk about them."*

---

### Add-interest dialog

Haiku parses the full picture — three selected tiles, the free-text addition, and the background text. The system mirrors back:

> *"I'm hearing solid state physics as the main theme, with semiconductors, superconductors, and topological insulators as specific angles within it. I also noted your calc and EM are rusty — I'll watch for refresher opportunities on those but won't put you through a curriculum before you see solid state content. Sound right?"*

They confirm. Four interest nodes created or linked: **Solid State Physics**, **Semiconductor Devices**, **Superconductivity**, **Topological Insulators**.

---

### Concept tours

**Solid State Physics** concept tour — six tiles from the megagraph's prerequisite edges:

| Concept | Gloss | Mark |
|---|---|---|
| Crystal lattice | The periodic arrangement of atoms that defines a solid's structure | Familiar |
| Bloch's theorem | Electrons in a periodic lattice take well-defined wave-like forms | Would want a refresh |
| Brillouin zone | The fundamental domain of momentum space for a periodic lattice | New to me |
| Band gap | The energy range with no allowed electron states, separating valence and conduction bands | Familiar |
| Fermi surface | The surface in momentum space separating occupied from unoccupied states | Think I have this (left as familiar) |
| Maxwell's equations in matter | How E and B fields behave inside materials | Would want a refresh |

**Semiconductor Devices** and **Superconductivity** tours follow, but are shorter — shared prerequisite nodes are deduplicated. A handful of new tiles each: Cooper pairs, critical temperature, Meissner effect for Superconductivity; carrier concentration, doping for Semiconductor Devices.

---

### Mode balance

Default 50/50. They leave it.

---

### Confirmation — first look at the megagraph

Four interest nodes appear, connected by edges, with a cluster of foundation nodes beneath: QM I, Statistical Mechanics, EM I, Multivariable Calculus, ODEs, Linear Algebra. Foundation nodes marked for refresh are subtly highlighted. Greyed-out adjacent regions sit at the edges: Crystal Lattices and Phonons, Magnetism, Optical Properties of Solids.

They tap the **Superconductivity** node. A panel slides up: description, subtopics listed (Meissner effect, BCS theory, Cooper pairs, Josephson junctions, flux quantization). Everything looks right. They close it and continue.

---

## Week 1 — Getting started

### Day 1

Three cards:

**Card 1: "What makes a solid?"** — Problem (teach intent)
A conceptual problem on why a periodic arrangement of atoms leads to fundamentally different electronic behaviour than a gas. No equations. The problem builds the intuition from scratch: why does periodicity matter? What does it mean for an electron to "belong" to a solid rather than a single atom?

**Card 2: "The band gap — why some materials conduct and others don't"** — Problem (teach intent)
Band theory explained conceptually before any calculation. The problem walks through the idea of allowed and forbidden energy ranges, then asks the user to argue why a material with a large band gap behaves as an insulator.

**Card 3: Multivariable Calculus refresher: gradient, divergence, curl** — Refresher (refresh intent)
Brief setup recalling what each operation means, then a few direct computations. Recall, not examination.

They work through the band gap problem. It clicks. They photograph their working, submit. The feedback is collegial:

> *"You've got the key intuition — periodicity of the lattice forces the gaps. Next we'll look at what happens when the gap is small enough that thermal energy can bridge it."*

They glance at the multivariable refresher and tap **"mark as refreshed, skip"** — they knew it, just needed to see the notation again.

### Days 2–5

The queue alternates between:
- Conceptual solid state problems: doping basics, what happens when impurities are added to a crystal
- EM I refreshers: Gauss's law, what Maxwell's equations actually say, boundary conditions in matter
- One paper: a *Physics Today* article on the history of the transistor — accessible, contextual, connects semiconductor interests to real history

Paper engagement questions are comprehension-focused: *"What was the key insight that made the transistor possible?"* Feedback is conversational, one turn each.

They reroll once — the third card was a Statistical Mechanics refresher and they weren't in the mood. The system notes the reroll. The replacement surfaces a semiconductor problem instead.

---

## Week 2 — Building depth

The queue has learned from week 1. The multivariable refresher was skipped as known. Statistical Mechanics got rerolled. The band gap and doping problems were fully engaged with.

**Queue shifts:**
- Semiconductor problems becoming more specific — the p-n junction concept, why charge migrates at the interface
- EM I refresher reappears: Maxwell's equations in matter (directly connected to the concept tour flag)
- **Statistical Mechanics refresher appears: Fermi-Dirac distribution** — the system has inferred this will be needed when semiconductor problems go deeper. Proactive timing.
- A second paper: a review article on semiconductor band structure, more technical than the transistor history piece

### Notable moment — Bloch's theorem

A problem on Bloch's theorem appears. It opens with a two-paragraph context:

> *"In a periodic crystal, electrons aren't confined to individual atoms — they exist as waves extending across the whole lattice. Bloch's theorem tells us the form these waves must take: the wavefunction must itself be periodic, modulated by a plane wave..."*

It builds the idea up before asking anything. The user works through it, uses the hint panel once, gets most of the way there. The feedback:

> *"You got the key step. The bit you hesitated on is exactly where most people do — the periodicity argument is subtle until it suddenly isn't."*

### Skill tree exploration (first time outside onboarding)

They open the skill tree. Their four interest nodes sit in a cluster, foundation nodes beneath. They tap the **EM I** tile. The panel opens — description and subtopics: Gauss's law, Faraday's law, Ampere's law, Maxwell's equations, boundary conditions, EM waves.

They tap **"request a refresher"** on boundary conditions — it wasn't in their original concept tour and they remember it being important for solid state. A focused problem appears in the next day's queue.

---

## Week 3 — First real math, first real papers

The EM refreshers have run. Bloch's theorem was engaged with. The queue now lets mathematics appear in problems proper.

### First math-requiring problem

**Density of states in the free electron model.** The setup builds it up carefully:

> *"We want to count how many electron states are available at each energy. In momentum space, each state occupies a small volume proportional to ℏ³. We'll work in three dimensions and use spherical symmetry to simplify..."*

The derivation requires a 3D integral in spherical coordinates — which the user now has the tools for, having refreshed multivariable calculus. They get through it. It takes longer. One hint used. The sense afterwards: *I worked through that and now I know what density of states actually means.*

### First real paper engagement

A 2006 review article on topological insulators appears — written for a broad physics audience, not specialists. Orienting concepts provided: topological order, Berry phase, time-reversal symmetry. Each with a one-line gloss. A *"want to refresh time-reversal symmetry first?"* link appears — they follow it, get a brief focused problem, then return to the paper.

They read externally, return, answer three questions:
- **Comprehension:** *"What distinguishes a topological insulator from an ordinary insulator in band theory terms?"*
- **Connective:** *"How does this relate to the band gap concept from week 1?"*
- **Open:** *"What surprised you?"*

The responses feel like a conversation. Feedback references what they said specifically.

### "Not ready yet"

A superconductivity problem appears — the second Josephson relation and phase dynamics. The mathematical apparatus hasn't been built yet. They tap **"not ready for this — come back later."**

The system re-queues it with a future priority. The queue accelerates BCS theory and Cooper pair material — conceptual first, then mathematical — ahead of the Josephson problem's return.

---

## Week 4 — The queue finds its rhythm

Four weeks in. The user has engaged with roughly 15 problems, 3 paper engagements, and 5 refreshers. The queue is well-calibrated.

### A typical daily view

**Card 1: "P-n junction: why a depletion region forms"** — Problem (teach/refresh intent)
The problem asks for a qualitative argument: what happens to charge carriers at the interface between p-type and n-type material, and why does an electric field develop? More mathematical than week 1 — uses carrier concentration and drift — but still builds each step up from the last.

**Card 2: "High-temperature superconductors: why BCS doesn't explain them"** — Paper (2019 *Physics Today* article)
Orienting concepts pitched at the user's current level — no longer entry-point glosses. Engagement questions mix comprehension and critical analysis: *"What experimental observation is most difficult to reconcile with conventional BCS theory?"*

**Card 3: QM I consolidation: particle in a box** — Consolidation
The user marked QM I comfortable at onboarding. The system surfaces a real calculation — solve the time-independent Schrödinger equation for a particle in a box, find the energy eigenvalues, sketch the first three wavefunctions. They get through it cleanly. The sense: *still have it.*

---

### Skill tree exploration

The user opens the skill tree. Greyed-out adjacent nodes are more visible now: Crystal Lattices and Phonons (bookmarked in week 1), Magnetism, Optical Properties of Solids.

They tap **Magnetism**. The panel opens:

> *"Why this matters: connects to spintronics and magnetic phases, both adjacent to your superconductors interest."*

They add it. The dialogic flow runs:

> *"Magnetism covers a few different angles — which sounds closest? (a) Classical magnetism and magnetic materials, (b) Quantum mechanical origins of magnetic ordering, (c) Magnetism in condensed matter contexts — spintronics, magnetic phases."*

They pick (c). A concept tour runs: five tiles, three of which they can immediately mark familiar.

---

### Cross-pollination

One of the three cards this week is a cross-pollination suggestion:

> *"Spintronics — others working in adjacent areas have been exploring this. Want to add it to your interests?"*

They're not ready for another thread yet. They dismiss it. The system waits before suggesting something similar.

---

### Profile page

They visit the profile page. 50/50 mode balance. Four interest nodes, now five with Magnetism. Under feedback they submit:

> *"My problems occasionally assume things I haven't seen."*

The system acknowledges it. The assumed-background dial tightens — generator instructions shift toward building up more before asking. The change is visible in subsequent problems, not in the UI.

---

## What this walkthrough demonstrates

By the end of week 4 the queue has a clear character:
- It knows the user is reconnecting rather than learning fresh
- It knows their math is coming back and times prerequisites proactively (EM refreshers before EM-dependent solid state problems; ODE refreshers approaching before BCS theory)
- It knows they respond well to conceptual problems that build up carefully before going mathematical
- It knows they want papers that treat them as a physicist, not a newcomer
- It has learned to hold off on Statistical Mechanics for now (rerolled once)

The Josephson relation problem is still waiting. It will return when the Cooper pair and phase-dynamics material has run. When it does, it will feel earnable rather than alien — the difference between the product working and the product failing.
