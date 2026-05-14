-- Seed 30 curated context hooks covering every canonical topic seeded in
-- 01_curriculum.sql. Safe to re-run: matches on slug and updates in place.
--
-- Each row carries:
--   slug              — stable identifier, used by the Python service for
--                       hook selection traces.
--   title             — short, citable headline.
--   summary_md        — 2–3 sentence seed; the problem generator expands this
--                       into the 2–4 paragraph "Historical context" block on
--                       the daily-problem page.
--   related_topic_ids — resolved from canonical_topics.slug via a subselect.
--   difficulty_band   — the band of topic this hook reads naturally at.
--   sources_json      — references (title/author/year). Operator can paste
--                       URLs later; we don't fabricate them in seed.
--
-- Apply with `npx supabase db push` after the Phase 3 migration.

insert into public.context_hooks (slug, title, summary_md, related_topic_ids, difficulty_band, sources_json)
select
  v.slug, v.title, v.summary_md,
  array(select id from public.canonical_topics where slug = any(v.topic_slugs)),
  v.difficulty_band, v.sources_json::jsonb
from (values

  -- ---- Classical mechanics & waves -----------------------------------------
  ('galileo-inclined-planes',
   $t$Galileo's inclined planes$t$,
   $ctx$In the early 1600s Galileo Galilei rolled bronze balls down polished wooden ramps to slow free fall enough to measure it, timing the descent with a water clock. He established that the distance covered grows as the square of the elapsed time — acceleration is constant and independent of mass. The result demolished the Aristotelian view that heavier objects fall faster and gave Newton the empirical bedrock for his second law.$ctx$,
   array['waves-oscillations', 'classical-mechanics'], 'intro',
   $src$[{"title":"Discorsi e dimostrazioni matematiche, intorno à due nuove scienze","author":"Galileo Galilei","year":1638}]$src$),

  ('newtons-principia',
   $t$Newton's Principia$t$,
   $ctx$Isaac Newton's Philosophiae Naturalis Principia Mathematica (1687) presented three laws of motion and a universal law of gravitation that together explained Kepler's planetary orbits, the tides, and projectile motion from a single set of axioms. Edmund Halley funded the publication after Newton, prompted to revisit his old calculations, showed that an inverse-square force produces ellipses. The book is the founding document of mathematical physics.$ctx$,
   array['classical-mechanics'], 'core',
   $src$[{"title":"Philosophiae Naturalis Principia Mathematica","author":"Isaac Newton","year":1687}]$src$),

  ('cavendish-weighing-earth',
   $t$Cavendish weighs the Earth$t$,
   $ctx$In 1797–98 Henry Cavendish suspended a delicate dumbbell from a wire inside a draft-proof box and measured the minute twist induced by lead balls placed nearby. The torsion let him compute the gravitational constant — and hence the mean density of the Earth — to within about 1% of the modern value. It was the first laboratory determination of G.$ctx$,
   array['classical-mechanics'], 'core',
   $src$[{"title":"Experiments to determine the Density of the Earth","author":"Henry Cavendish","year":1798}]$src$),

  ('kepler-mars-orbit',
   $t$Kepler and the orbit of Mars$t$,
   $ctx$Johannes Kepler spent eight years on Tycho Brahe's Mars data before admitting in 1605 that the orbit was not a circle. The eccentricity is only 0.093 — small enough that earlier astronomers had compensated with epicycles — but Brahe's arc-minute precision left no room. Kepler's three laws pinned down the empirical content that Newton would derive from inverse-square gravity sixty years later.$ctx$,
   array['classical-mechanics', 'odes'], 'core',
   $src$[{"title":"Astronomia Nova","author":"Johannes Kepler","year":1609}]$src$),

  ('foucault-pendulum',
   $t$Foucault's pendulum$t$,
   $ctx$In 1851 Léon Foucault hung a 28 kg iron bob from a 67 m wire under the dome of the Paris Panthéon. The plane of swing slowly rotated relative to the floor — direct visual proof that the Earth turns beneath the pendulum. The rotation rate at latitude φ is ω sin φ, a clean consequence of working in a non-inertial rotating frame.$ctx$,
   array['classical-mechanics', 'waves-oscillations'], 'core',
   $src$[{"title":"Démonstration physique du mouvement de rotation de la Terre","author":"Léon Foucault","year":1851}]$src$),

  -- ---- Lagrangian / Hamiltonian --------------------------------------------
  ('noether-theorem',
   $t$Noether's theorem$t$,
   $ctx$Emmy Noether's 1918 paper showed that every continuous symmetry of an action functional implies a conservation law: time translation gives energy, spatial translation gives momentum, rotational symmetry gives angular momentum. Einstein called it "a piece of mathematical thinking of penetrating depth." The theorem is the conceptual centerpiece of Lagrangian field theory and the reason symmetries dominate modern physics.$ctx$,
   array['lagrangian-mechanics'], 'advanced',
   $src$[{"title":"Invariante Variationsprobleme","author":"Emmy Noether","year":1918}]$src$),

  ('lagrange-mecanique-analytique',
   $t$Lagrange's Mécanique analytique$t$,
   $ctx$Joseph-Louis Lagrange's Mécanique analytique (1788) recast Newtonian mechanics with no diagrams — only the calculus of variations applied to a single function L = T − V. The Euler–Lagrange equations follow from extremising the action, and the formulation generalises trivially to constrained systems, field theory, and eventually general relativity.$ctx$,
   array['lagrangian-mechanics', 'calculus-2'], 'advanced',
   $src$[{"title":"Mécanique analytique","author":"Joseph-Louis Lagrange","year":1788}]$src$),

  -- ---- Special relativity --------------------------------------------------
  ('michelson-morley',
   $t$The Michelson–Morley experiment$t$,
   $ctx$Albert A. Michelson and Edward W. Morley used a 1.2 m interferometer floating on mercury in a Cleveland basement to look for the Earth's motion through the luminiferous ether. The null result — fringe shift well below the predicted threshold — could not be explained by ether-drag or contraction hypotheses without strain, and forced the postulate that the speed of light is the same in every inertial frame.$ctx$,
   array['special-relativity', 'optics'], 'advanced',
   $src$[{"title":"On the Relative Motion of the Earth and the Luminiferous Ether","author":"Michelson and Morley","year":1887}]$src$),

  ('einstein-1905',
   $t$Einstein's annus mirabilis$t$,
   $ctx$In a single year Albert Einstein — a 26-year-old patent clerk in Bern — published four papers that founded modern physics: the photoelectric effect (quanta of light), Brownian motion (atomistic proof), special relativity (the kinematics of light), and the mass–energy equivalence E = mc². All four were written with no university affiliation, in evenings after work.$ctx$,
   array['special-relativity'], 'advanced',
   $src$[{"title":"Zur Elektrodynamik bewegter Körper","author":"Albert Einstein","year":1905}]$src$),

  ('hafele-keating',
   $t$Hafele–Keating atomic clocks$t$,
   $ctx$In 1971 Joseph Hafele and Richard Keating flew four caesium atomic clocks around the world on commercial airliners — once eastward, once westward — and compared them to ground-based reference clocks. The measured time differences of tens of nanoseconds matched the combined special- and general-relativistic predictions to within experimental error, providing the first direct test with macroscopic clocks.$ctx$,
   array['special-relativity'], 'advanced',
   $src$[{"title":"Around-the-World Atomic Clocks: Predicted and Observed Relativistic Time Gains","author":"Hafele and Keating","year":1972}]$src$),

  -- ---- Electromagnetism ----------------------------------------------------
  ('coulomb-torsion-balance',
   $t$Coulomb's torsion balance$t$,
   $ctx$In 1785 Charles-Augustin de Coulomb published the inverse-square law of electrostatics, established by mounting a charged pith ball on the end of a delicate torsion fibre and measuring the angle of twist as a second ball approached. The same torsion-balance technique he developed for this work would later be adapted by Cavendish for gravitation.$ctx$,
   array['electromagnetism-1'], 'core',
   $src$[{"title":"Premier mémoire sur l'électricité et le magnétisme","author":"Charles-Augustin de Coulomb","year":1785}]$src$),

  ('faraday-induction',
   $t$Faraday discovers induction$t$,
   $ctx$In August 1831 Michael Faraday wound two coils around opposite sides of a soft iron ring. Closing the primary circuit produced a brief deflection in the secondary's galvanometer; opening it produced another in the opposite direction. The discovery — that a changing magnetic flux drives a current — underlies every generator and transformer ever built.$ctx$,
   array['electromagnetism-1'], 'core',
   $src$[{"title":"Experimental Researches in Electricity, Series I","author":"Michael Faraday","year":1832}]$src$),

  ('maxwell-unification',
   $t$Maxwell unifies electricity, magnetism, and light$t$,
   $ctx$James Clerk Maxwell's 1865 paper A Dynamical Theory of the Electromagnetic Field presented twenty equations — later condensed by Heaviside to four — unifying electricity, magnetism, and light. The displacement-current term Maxwell added to Ampère's law made the equations consistent and predicted electromagnetic waves travelling at exactly the measured speed of light: "we can scarcely avoid the inference that light consists in the transverse undulations of the same medium."$ctx$,
   array['electromagnetism-2'], 'advanced',
   $src$[{"title":"A Dynamical Theory of the Electromagnetic Field","author":"James Clerk Maxwell","year":1865}]$src$),

  ('hertz-radio-waves',
   $t$Hertz detects radio waves$t$,
   $ctx$In 1887–88 Heinrich Hertz produced and detected the electromagnetic waves Maxwell had predicted twenty years earlier. A spark gap driven by an induction coil radiated waves around 60 cm in length; a second spark gap a few metres away picked them up. Hertz measured their speed, polarisation, and refraction — and famously said he saw "no use whatsoever" for the discovery.$ctx$,
   array['electromagnetism-2', 'optics'], 'advanced',
   $src$[{"title":"Über sehr schnelle elektrische Schwingungen","author":"Heinrich Hertz","year":1887}]$src$),

  -- ---- Optics --------------------------------------------------------------
  ('young-double-slit',
   $t$Young's double-slit$t$,
   $ctx$In 1801 Thomas Young presented to the Royal Society a simple experiment: light from a single source split into two narrow slits produced alternating bright and dark bands on a screen behind them. The interference pattern was straightforward to explain if light is a wave, impossible if it is a stream of corpuscles. A century later the same experiment would be repeated with electrons — and the pattern survived.$ctx$,
   array['optics', 'quantum-mechanics-1'], 'intro',
   $src$[{"title":"On the Theory of Light and Colours (Bakerian Lecture)","author":"Thomas Young","year":1802}]$src$),

  ('fraunhofer-spectral-lines',
   $t$Fraunhofer's spectral lines$t$,
   $ctx$In 1814 Joseph von Fraunhofer, a Bavarian optician, mapped 574 dark lines in the spectrum of the Sun using diffraction gratings he had ruled himself. The lines were unexplained for half a century until Kirchhoff and Bunsen recognised them as absorption signatures of specific elements — establishing astrophysical spectroscopy and providing the empirical input that Bohr's atomic model would later have to reproduce.$ctx$,
   array['optics', 'quantum-mechanics-1'], 'core',
   $src$[{"title":"Bestimmung des Brechungs- und des Farben-Zerstreuungs-Vermögens verschiedener Glasarten","author":"Joseph von Fraunhofer","year":1814}]$src$),

  -- ---- Thermodynamics & statistical mechanics ------------------------------
  ('carnot-engine',
   $t$Carnot's heat engine$t$,
   $ctx$Sadi Carnot's 1824 essay Réflexions sur la puissance motrice du feu analysed an idealised heat engine — two isothermal and two adiabatic legs — and showed that its efficiency depends only on the temperatures of the hot and cold reservoirs, not the working substance. The Carnot bound η = 1 − T_c/T_h is the most important inequality in thermodynamics and led directly to the concept of entropy.$ctx$,
   array['thermodynamics'], 'core',
   $src$[{"title":"Réflexions sur la puissance motrice du feu","author":"Sadi Carnot","year":1824}]$src$),

  ('joule-mechanical-heat',
   $t$Joule's mechanical equivalent of heat$t$,
   $ctx$Between 1843 and 1845 James Prescott Joule, a Manchester brewer's son, used a falling weight to turn a paddle wheel inside an insulated bucket of water and measured the temperature rise. The constant ratio of mechanical work to thermal energy — about 4.18 J per calorie — established that heat is a form of energy and not a separate fluid (caloric), setting up the first law of thermodynamics.$ctx$,
   array['thermodynamics'], 'core',
   $src$[{"title":"On the Mechanical Equivalent of Heat","author":"James Prescott Joule","year":1845}]$src$),

  ('boltzmann-entropy',
   $t$Boltzmann's tomb: S = k log W$t$,
   $ctx$Ludwig Boltzmann's tomb in Vienna's Zentralfriedhof carries a single equation: S = k log W. Entropy, he showed in 1877, is proportional to the logarithm of the number of microstates consistent with a given macrostate. The statistical interpretation rescued the second law from the apparent paradox of reversible microscopic dynamics, though Boltzmann himself died before it was widely accepted.$ctx$,
   array['statistical-mechanics', 'thermodynamics'], 'advanced',
   $src$[{"title":"Über die Beziehung zwischen dem zweiten Hauptsatze der mechanischen Wärmetheorie und der Wahrscheinlichkeitsrechnung","author":"Ludwig Boltzmann","year":1877}]$src$),

  ('planck-blackbody',
   $t$Planck and the black-body spectrum$t$,
   $ctx$On December 14, 1900 Max Planck derived a formula for the spectrum of black-body radiation by assuming — as "an act of desperation" — that oscillators in the cavity walls exchange energy only in discrete packets E = hν. The constant h ≈ 6.626 × 10⁻³⁴ J·s, introduced for mathematical convenience, turned out to mark the dividing line between classical and quantum physics.$ctx$,
   array['quantum-mechanics-1', 'statistical-mechanics'], 'advanced',
   $src$[{"title":"Zur Theorie des Gesetzes der Energieverteilung im Normalspektrum","author":"Max Planck","year":1901}]$src$),

  -- ---- Quantum mechanics ---------------------------------------------------
  ('millikan-oil-drop',
   $t$Millikan's oil-drop experiment$t$,
   $ctx$Between 1909 and 1913 Robert Millikan suspended tiny oil droplets between charged plates and measured the voltage that held each one motionless against gravity. The charges always came in integer multiples of a single value e ≈ 1.6 × 10⁻¹⁹ C — the elementary charge. Millikan's notebooks later showed he had quietly discarded runs he thought unreliable, a now-textbook example of selection bias.$ctx$,
   array['quantum-mechanics-1', 'electromagnetism-1'], 'core',
   $src$[{"title":"On the Elementary Electrical Charge and the Avogadro Constant","author":"Robert A. Millikan","year":1913}]$src$),

  ('rutherford-gold-foil',
   $t$Rutherford's gold-foil experiment$t$,
   $ctx$Working with Hans Geiger and Ernest Marsden, Ernest Rutherford fired alpha particles at a thin gold foil and observed a small but unmistakable fraction scattered backwards. "It was almost as incredible," he later said, "as if you fired a fifteen-inch shell at a piece of tissue paper and it came back and hit you." The plum-pudding atom was dead; the nuclear atom was born.$ctx$,
   array['quantum-mechanics-1'], 'core',
   $src$[{"title":"The Scattering of α and β Particles by Matter and the Structure of the Atom","author":"Ernest Rutherford","year":1911}]$src$),

  ('bohr-hydrogen-spectrum',
   $t$Bohr's atom and the hydrogen spectrum$t$,
   $ctx$Niels Bohr's 1913 model imposed an ad hoc quantisation condition — angular momentum in integer multiples of ℏ — on Rutherford's nuclear atom, and immediately reproduced the Rydberg formula for the hydrogen spectrum to four decimal places. The agreement was so good it could not be dismissed even though the model violated classical electrodynamics on its face.$ctx$,
   array['quantum-mechanics-1', 'optics'], 'core',
   $src$[{"title":"On the Constitution of Atoms and Molecules","author":"Niels Bohr","year":1913}]$src$),

  ('davisson-germer',
   $t$Davisson–Germer and matter waves$t$,
   $ctx$In 1927 Clinton Davisson and Lester Germer at Bell Labs scattered low-energy electrons off a nickel single-crystal and observed an interference pattern matching the de Broglie wavelength λ = h/p. Matter, not just light, exhibited wave behaviour — the experimental confirmation of de Broglie's 1924 thesis and the empirical foundation of wave mechanics.$ctx$,
   array['quantum-mechanics-1'], 'core',
   $src$[{"title":"Diffraction of Electrons by a Crystal of Nickel","author":"Davisson and Germer","year":1927}]$src$),

  ('stern-gerlach',
   $t$Stern–Gerlach and the quantisation of spin$t$,
   $ctx$In 1922 Otto Stern and Walther Gerlach passed a beam of neutral silver atoms through an inhomogeneous magnetic field. Classical physics predicted a continuous smear; the actual result was two discrete spots. Spin angular momentum is quantised, takes only the values ±ℏ/2 for a spin-½ particle, and (as Pauli would later insist) has no classical analogue.$ctx$,
   array['quantum-mechanics-2'], 'advanced',
   $src$[{"title":"Der experimentelle Nachweis der Richtungsquantelung im Magnetfeld","author":"Stern and Gerlach","year":1922}]$src$),

  ('bell-inequality',
   $t$Bell's inequality and entanglement$t$,
   $ctx$In 1964 John Bell derived an inequality that any local hidden-variable theory must obey but that quantum mechanics violates for specific entangled states. Alain Aspect's 1982 experiments, with loophole-free tests following in the 2010s, confirmed the quantum prediction. The 2022 Nobel Prize recognised this line of work; local realism is empirically dead.$ctx$,
   array['quantum-mechanics-2'], 'advanced',
   $src$[{"title":"On the Einstein-Podolsky-Rosen Paradox","author":"John S. Bell","year":1964}]$src$),

  -- ---- Math: analysis, PDEs, complex --------------------------------------
  ('l-hopital-bernoulli',
   $t$L'Hôpital's rule (and Bernoulli's bill)$t$,
   $ctx$The rule for evaluating 0/0 limits using derivatives — taught in every Calculus I class — appears in the 1696 textbook of Guillaume de l'Hôpital, but was almost certainly discovered by Johann Bernoulli, whom l'Hôpital paid a retainer for unpublished mathematics. The arrangement, exposed two centuries later when Bernoulli's correspondence was published, is an early case study in academic credit and an entry point to the rigorous treatment of indeterminate limits.$ctx$,
   array['calculus-1'], 'intro',
   $src$[{"title":"Analyse des Infiniment Petits pour l'Intelligence des Lignes Courbes","author":"Guillaume de l'Hôpital","year":1696}]$src$),

  ('fourier-heat-equation',
   $t$Fourier's theory of heat$t$,
   $ctx$Joseph Fourier's Théorie analytique de la chaleur (1822) introduced the heat equation ∂u/∂t = α ∇²u and the technique that bears his name: any periodic function can be decomposed into a sum of sines and cosines. The mathematical fallout — completeness, convergence, the very notion of a function — kept analysts busy for the rest of the nineteenth century.$ctx$,
   array['pdes', 'calculus-2'], 'advanced',
   $src$[{"title":"Théorie analytique de la chaleur","author":"Joseph Fourier","year":1822}]$src$),

  ('cauchy-rigorous-analysis',
   $t$Cauchy and the rigorisation of analysis$t$,
   $ctx$Augustin-Louis Cauchy's Cours d'Analyse (1821) replaced the loose infinitesimals of the early calculus with explicit ε–δ definitions of limits, continuity, and convergence. Cauchy's later residue calculus turned contour integration into a working tool; together with Weierstrass's later refinements his work is the source of every modern analysis textbook.$ctx$,
   array['real-analysis', 'complex-analysis'], 'advanced',
   $src$[{"title":"Cours d'Analyse de l'École Royale Polytechnique","author":"Augustin-Louis Cauchy","year":1821}]$src$),

  ('multivariable-cavendish-field',
   $t$Gauss, divergence, and the geomagnetic field$t$,
   $ctx$In the 1830s Carl Friedrich Gauss, collaborating with Wilhelm Weber, set up a global network of magnetic observatories and derived the first spherical-harmonic decomposition of the Earth's magnetic field. The work made essential use of the divergence theorem (now bearing his name) and the potential theory that underlies most of multivariable calculus.$ctx$,
   array['multivariable-calculus', 'electromagnetism-1'], 'core',
   $src$[{"title":"Allgemeine Theorie des Erdmagnetismus","author":"Carl Friedrich Gauss","year":1838}]$src$),

  ('linear-algebra-cayley-hamilton',
   $t$Cayley, Hamilton, and the algebra of matrices$t$,
   $ctx$In 1858 Arthur Cayley introduced the matrix as a formal object — addition, multiplication, inverses — separate from any system of linear equations. The Cayley–Hamilton theorem, that every square matrix satisfies its own characteristic polynomial, gave the new algebra a deep structural result and helped seed twentieth-century quantum mechanics, where matrices became operators on Hilbert space.$ctx$,
   array['linear-algebra'], 'core',
   $src$[{"title":"A Memoir on the Theory of Matrices","author":"Arthur Cayley","year":1858}]$src$),

  -- ---- Probability & statistics --------------------------------------------
  ('gauss-normal-distribution',
   $t$Gauss, Ceres, and the normal distribution$t$,
   $ctx$In 1801 the asteroid Ceres was lost behind the Sun shortly after discovery. Carl Friedrich Gauss, then 24, computed its orbit from a few weeks of observations using a method (least squares) he had developed but not yet published. The error analysis required justified the bell curve — now the normal distribution — as the natural model for measurement error, and made Gauss a celebrity overnight when Ceres was recovered exactly where he predicted.$ctx$,
   array['probability', 'statistics'], 'core',
   $src$[{"title":"Theoria Motus Corporum Coelestium","author":"Carl Friedrich Gauss","year":1809}]$src$),

  ('john-snow-cholera',
   $t$John Snow and the Broad Street pump$t$,
   $ctx$In the 1854 Soho cholera outbreak John Snow plotted deaths on a street map of London and noticed the cluster centred on the Broad Street water pump. After the pump handle was removed the outbreak subsided. The episode — often cited as the founding case of epidemiology — is a clean example of a spatial natural experiment, and predates the germ theory of disease by twenty years.$ctx$,
   array['statistics'], 'core',
   $src$[{"title":"On the Mode of Communication of Cholera","author":"John Snow","year":1855}]$src$),

  ('bayes-essay',
   $t$Bayes' essay on inverse probability$t$,
   $ctx$Thomas Bayes' An Essay towards solving a Problem in the Doctrine of Chances was read at the Royal Society in 1763, two years after his death, by his friend Richard Price. It posed the inverse problem: given an observed outcome, what does one infer about the underlying probability? The theorem that bears his name — P(H|D) ∝ P(D|H) P(H) — sat in relative obscurity for nearly two centuries before becoming a foundation of modern statistics.$ctx$,
   array['probability', 'statistics'], 'core',
   $src$[{"title":"An Essay towards solving a Problem in the Doctrine of Chances","author":"Thomas Bayes (posthumous, ed. Richard Price)","year":1763}]$src$)

) as v(slug, title, summary_md, topic_slugs, difficulty_band, sources_json)
on conflict (slug) do update set
  title             = excluded.title,
  summary_md        = excluded.summary_md,
  related_topic_ids = excluded.related_topic_ids,
  difficulty_band   = excluded.difficulty_band,
  sources_json      = excluded.sources_json;
