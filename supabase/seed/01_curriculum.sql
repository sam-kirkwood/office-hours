-- Seed canonical topics and prerequisite edges.
-- Safe to run multiple times — uses ON CONFLICT DO UPDATE so re-running picks
-- up changes (subtopics, descriptions, etc.) on existing rows.

insert into public.canonical_topics (slug, title, description, difficulty_band, domain, subtopics) values
  -- Math -----------------------------------------------------------------------
  ('calculus-1',
   'Calculus I',
   'Limits, continuity, derivatives, and the basics of integration for single-variable functions. The quantitative foundation of all physical science.',
   'intro', 'math',
   $$[{"slug":"limits-continuity","title":"Limits & continuity"},{"slug":"derivatives","title":"Derivatives & rules"},{"slug":"applications","title":"Optimisation & related rates"},{"slug":"integration-basics","title":"Integrals & antiderivatives"},{"slug":"fundamental-theorem","title":"Fundamental theorem of calculus"}]$$::jsonb),

  ('calculus-2',
   'Calculus II',
   'Integration techniques, improper integrals, sequences, infinite series, and Taylor expansions.',
   'core', 'math',
   $$[{"slug":"integration-techniques","title":"Integration techniques"},{"slug":"improper-integrals","title":"Improper integrals"},{"slug":"sequences-series","title":"Sequences & series"},{"slug":"convergence-tests","title":"Convergence tests"},{"slug":"taylor-series","title":"Taylor & Maclaurin series"}]$$::jsonb),

  ('multivariable-calculus',
   'Multivariable Calculus',
   'Functions of several variables, partial derivatives, gradients, multiple integrals, line and surface integrals, div/curl/grad.',
   'core', 'math',
   $$[{"slug":"partial-derivatives","title":"Partial derivatives & gradients"},{"slug":"multiple-integrals","title":"Multiple integrals"},{"slug":"line-surface-integrals","title":"Line & surface integrals"},{"slug":"vector-fields","title":"Vector fields, div & curl"},{"slug":"integral-theorems","title":"Green''s, Stokes'', divergence theorems"}]$$::jsonb),

  ('linear-algebra',
   'Linear Algebra',
   'Vectors, matrices, linear transformations, determinants, eigenvalues and eigenvectors, inner product spaces.',
   'core', 'math',
   $$[{"slug":"vectors-matrices","title":"Vectors & matrices"},{"slug":"linear-transformations","title":"Linear transformations"},{"slug":"determinants","title":"Determinants"},{"slug":"eigenvalues","title":"Eigenvalues & eigenvectors"},{"slug":"inner-product-spaces","title":"Inner product spaces"}]$$::jsonb),

  ('odes',
   'Ordinary Differential Equations',
   'First and second order ODEs, systems of ODEs, Laplace transforms, phase plane analysis, stability.',
   'core', 'math',
   $$[{"slug":"first-order","title":"First-order ODEs"},{"slug":"second-order-linear","title":"Second-order linear ODEs"},{"slug":"systems","title":"Systems of ODEs"},{"slug":"laplace-transforms","title":"Laplace transforms"},{"slug":"phase-plane","title":"Phase plane & stability"}]$$::jsonb),

  ('pdes',
   'Partial Differential Equations',
   'Heat equation, wave equation, Laplace equation, separation of variables, Fourier methods, characteristics.',
   'advanced', 'math',
   $$[{"slug":"heat-equation","title":"Heat equation"},{"slug":"wave-equation","title":"Wave equation"},{"slug":"laplace-equation","title":"Laplace & Poisson equations"},{"slug":"separation-of-variables","title":"Separation of variables"},{"slug":"fourier-methods","title":"Fourier series & transforms"}]$$::jsonb),

  ('real-analysis',
   'Real Analysis',
   'Rigorous foundations of calculus: metric spaces, limits, continuity, differentiability, Riemann and Lebesgue integration.',
   'advanced', 'math',
   $$[{"slug":"metric-spaces","title":"Metric & topological spaces"},{"slug":"sequences-series-rigour","title":"Sequences & series (rigorous)"},{"slug":"continuity-differentiability","title":"Continuity & differentiability"},{"slug":"riemann-integration","title":"Riemann integration"},{"slug":"lebesgue-integration","title":"Lebesgue integration"}]$$::jsonb),

  ('complex-analysis',
   'Complex Analysis',
   'Complex differentiability, Cauchy–Riemann equations, contour integration, Cauchy''s theorem, residues, conformal mapping.',
   'advanced', 'math',
   $$[{"slug":"complex-differentiability","title":"Complex differentiability"},{"slug":"cauchy-riemann","title":"Cauchy–Riemann equations"},{"slug":"contour-integration","title":"Contour integration"},{"slug":"cauchy-theorem","title":"Cauchy''s theorem & integral formula"},{"slug":"residues","title":"Residues & poles"}]$$::jsonb),

  ('probability',
   'Probability Theory',
   'Probability spaces, random variables, distributions, expectation, conditional probability, law of large numbers, central limit theorem.',
   'core', 'math',
   $$[{"slug":"probability-spaces","title":"Probability spaces & events"},{"slug":"random-variables","title":"Random variables & distributions"},{"slug":"expectation-variance","title":"Expectation & variance"},{"slug":"conditional-probability","title":"Conditional probability & independence"},{"slug":"limit-theorems","title":"Law of large numbers & CLT"}]$$::jsonb),

  ('statistics',
   'Statistics',
   'Statistical inference, estimation, hypothesis testing, confidence intervals, regression, Bayesian methods.',
   'core', 'math',
   $$[{"slug":"estimation","title":"Point & interval estimation"},{"slug":"hypothesis-testing","title":"Hypothesis testing"},{"slug":"confidence-intervals","title":"Confidence intervals"},{"slug":"regression","title":"Linear regression"},{"slug":"bayesian","title":"Bayesian inference"}]$$::jsonb),

  -- Physics --------------------------------------------------------------------
  ('waves-oscillations',
   'Waves & Oscillations',
   'Simple harmonic motion, damped and driven oscillators, resonance, wave equation, standing waves, coupled oscillators.',
   'intro', 'physics',
   $$[{"slug":"shm","title":"Simple harmonic motion"},{"slug":"damped-driven","title":"Damped & driven oscillators"},{"slug":"wave-equation-basics","title":"Wave equation basics"},{"slug":"standing-waves","title":"Standing waves & boundaries"},{"slug":"coupled","title":"Coupled oscillators & normal modes"}]$$::jsonb),

  ('classical-mechanics',
   'Classical Mechanics',
   'Newton''s laws, energy and momentum conservation, gravitation, rigid body motion, central force problems, non-inertial frames.',
   'core', 'physics',
   $$[{"slug":"newtons-laws","title":"Newton''s laws & free-body diagrams"},{"slug":"energy","title":"Work, energy & conservation"},{"slug":"momentum","title":"Momentum & collisions"},{"slug":"rotation","title":"Rotation & angular momentum"},{"slug":"central-force","title":"Central force problems"}]$$::jsonb),

  ('lagrangian-mechanics',
   'Lagrangian & Hamiltonian Mechanics',
   'Principle of least action, Euler–Lagrange equations, symmetries and conservation laws, Hamiltonian mechanics, Poisson brackets.',
   'advanced', 'physics',
   $$[{"slug":"least-action","title":"Principle of least action"},{"slug":"euler-lagrange","title":"Euler–Lagrange equations"},{"slug":"symmetries","title":"Symmetries & Noether''s theorem"},{"slug":"hamiltonian","title":"Hamiltonian mechanics"},{"slug":"poisson-brackets","title":"Poisson brackets"}]$$::jsonb),

  ('special-relativity',
   'Special Relativity',
   'Postulates of special relativity, Lorentz transformations, spacetime intervals, time dilation, length contraction, relativistic dynamics.',
   'advanced', 'physics',
   $$[{"slug":"postulates","title":"Postulates & Lorentz transformations"},{"slug":"time-dilation","title":"Time dilation & length contraction"},{"slug":"spacetime-intervals","title":"Spacetime intervals & causality"},{"slug":"relativistic-dynamics","title":"Relativistic momentum & energy"},{"slug":"four-vectors","title":"Four-vectors"}]$$::jsonb),

  ('electromagnetism-1',
   'Electromagnetism I',
   'Electrostatics, Gauss''s law, electric potential, magnetostatics, Biot–Savart law, Ampère''s law, Faraday''s law.',
   'core', 'physics',
   $$[{"slug":"electrostatics","title":"Electrostatics & Coulomb''s law"},{"slug":"gauss-law","title":"Gauss''s law & electric potential"},{"slug":"magnetostatics","title":"Magnetostatics & Biot–Savart"},{"slug":"faradays-law","title":"Faraday''s law & induction"},{"slug":"circuits","title":"Circuits & RLC"}]$$::jsonb),

  ('electromagnetism-2',
   'Electromagnetism II',
   'Maxwell''s equations in full, electromagnetic waves, energy and momentum of fields, radiation, gauges and potentials.',
   'advanced', 'physics',
   $$[{"slug":"maxwell-equations","title":"Maxwell''s equations (full)"},{"slug":"em-waves","title":"Electromagnetic waves"},{"slug":"energy-momentum","title":"Energy & momentum of fields"},{"slug":"radiation","title":"Radiation from accelerating charges"},{"slug":"gauges-potentials","title":"Gauges & potentials"}]$$::jsonb),

  ('optics',
   'Optics',
   'Geometric optics, ray tracing, wave optics, interference, diffraction, polarisation, coherence.',
   'core', 'physics',
   $$[{"slug":"geometric-optics","title":"Geometric optics & ray tracing"},{"slug":"wave-optics","title":"Wave optics & interference"},{"slug":"diffraction","title":"Diffraction"},{"slug":"polarisation","title":"Polarisation"},{"slug":"coherence","title":"Coherence"}]$$::jsonb),

  ('thermodynamics',
   'Thermodynamics',
   'Zeroth, first, second, and third laws, entropy, free energy, thermodynamic potentials, phase transitions, thermodynamic cycles.',
   'core', 'physics',
   $$[{"slug":"laws","title":"Zeroth, first, second, third laws"},{"slug":"entropy","title":"Entropy"},{"slug":"free-energy","title":"Free energy & potentials"},{"slug":"phase-transitions","title":"Phase transitions"},{"slug":"cycles","title":"Thermodynamic cycles & engines"}]$$::jsonb),

  ('statistical-mechanics',
   'Statistical Mechanics',
   'Microstates and macrostates, partition functions, Boltzmann, Fermi–Dirac, and Bose–Einstein statistics, phase transitions.',
   'advanced', 'physics',
   $$[{"slug":"microstates","title":"Microstates & macrostates"},{"slug":"partition-functions","title":"Partition functions"},{"slug":"boltzmann","title":"Boltzmann statistics"},{"slug":"quantum-statistics","title":"Fermi–Dirac & Bose–Einstein"},{"slug":"phase-transitions-statmech","title":"Phase transitions"}]$$::jsonb),

  ('quantum-mechanics-1',
   'Quantum Mechanics I',
   'Wave functions, Schrödinger equation, probability interpretation, operators and observables, uncertainty principle, 1D problems, hydrogen atom.',
   'core', 'physics',
   $$[{"slug":"wave-functions","title":"Wave functions & Schrödinger equation"},{"slug":"operators","title":"Operators & observables"},{"slug":"one-d-problems","title":"1D problems & potential wells"},{"slug":"hydrogen-atom","title":"Hydrogen atom"},{"slug":"uncertainty","title":"Uncertainty principle"}]$$::jsonb),

  ('quantum-mechanics-2',
   'Quantum Mechanics II',
   'Angular momentum, spin, identical particles, perturbation theory, variational methods, scattering theory.',
   'advanced', 'physics',
   $$[{"slug":"angular-momentum","title":"Angular momentum & spin"},{"slug":"identical-particles","title":"Identical particles & symmetry"},{"slug":"perturbation-theory","title":"Perturbation theory"},{"slug":"variational","title":"Variational methods"},{"slug":"scattering","title":"Scattering theory"}]$$::jsonb)

on conflict (slug) do update set
  title = excluded.title,
  description = excluded.description,
  difficulty_band = excluded.difficulty_band,
  domain = excluded.domain,
  subtopics = excluded.subtopics;


-- Prerequisite edges ----------------------------------------------------------
-- Using slug lookups so the file is readable and order-independent.

insert into public.canonical_edges (prerequisite_topic_id, dependent_topic_id, weight)
select p.id, d.id, 1
from public.canonical_topics p
join public.canonical_topics d on true
where (p.slug, d.slug) in (
  -- Math chain
  ('calculus-1',            'calculus-2'),
  ('calculus-1',            'classical-mechanics'),
  ('calculus-1',            'waves-oscillations'),
  ('calculus-2',            'multivariable-calculus'),
  ('calculus-2',            'odes'),
  ('calculus-2',            'probability'),
  ('calculus-2',            'thermodynamics'),
  ('multivariable-calculus','electromagnetism-1'),
  ('multivariable-calculus','pdes'),
  ('multivariable-calculus','lagrangian-mechanics'),
  ('linear-algebra',        'quantum-mechanics-1'),
  ('linear-algebra',        'real-analysis'),
  ('linear-algebra',        'statistics'),
  ('odes',                  'pdes'),
  ('odes',                  'lagrangian-mechanics'),
  ('odes',                  'quantum-mechanics-2'),
  -- Physics chain
  ('classical-mechanics',   'lagrangian-mechanics'),
  ('classical-mechanics',   'special-relativity'),
  ('waves-oscillations',    'quantum-mechanics-1'),
  ('waves-oscillations',    'optics'),
  ('electromagnetism-1',    'electromagnetism-2'),
  ('electromagnetism-1',    'optics'),
  ('probability',           'statistics'),
  ('probability',           'statistical-mechanics'),
  ('thermodynamics',        'statistical-mechanics'),
  ('quantum-mechanics-1',   'quantum-mechanics-2'),
  ('quantum-mechanics-1',   'statistical-mechanics'),
  ('real-analysis',         'complex-analysis')
)
on conflict (prerequisite_topic_id, dependent_topic_id) do nothing;
