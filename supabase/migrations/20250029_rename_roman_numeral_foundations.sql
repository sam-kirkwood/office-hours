-- Phase 10-rev Step 9 follow-up — rename the I/II-suffixed foundation node
-- titles to descriptive forms that indicate what's inside each topic and
-- where its boundary sits.
--
-- The persona walkthroughs showed "Quantum Mechanics I" / "II" read as
-- university-catalogue entries rather than as content signals — a working
-- professional looking at the tile can't tell from the name whether spin is
-- inside or outside. Renames are title-only; slugs stay as IDs, descriptions
-- and subtopics already describe the actual content correctly.
--
-- No foreign-key impact: every reference is by UUID. Safe to apply against
-- live data.

update public.nodes
   set title = 'Calculus: Derivatives and Basic Integration'
 where slug = 'calculus-1';

update public.nodes
   set title = 'Calculus: Integration Techniques and Series'
 where slug = 'calculus-2';

update public.nodes
   set title = 'Electromagnetism: Static Fields and Maxwell''s Equations'
 where slug = 'electromagnetism-1';

update public.nodes
   set title = 'Quantum Mechanics: Wavefunctions, Operators, and the Hydrogen Atom'
 where slug = 'quantum-mechanics-1';
