// Canonical Stage 1 chips, sub-areas, and relationship cards
// (survey-and-difficulty-design.md §1.2, extended in 2c-tweak for richer
// personalisation per-domain).
//
// Source of truth — read by BackgroundForm, the foundations stage label
// framing, and (via the survey route) the Python /survey/suggest-interests
// endpoint's Haiku rerank prompt. Sub-area chip keys are stable; their
// human-readable labels live alongside.

export type DomainKey =
  | "physics"
  | "mathematics"
  | "engineering"
  | "computation"
  | "biology"
  | "chemistry";

export interface DomainDef {
  key: DomainKey;
  label: string;
  subareas: ReadonlyArray<{ key: string; label: string }>;
}

export const DOMAINS: ReadonlyArray<DomainDef> = [
  {
    key: "physics",
    label: "Physics",
    subareas: [
      { key: "classical-mechanics", label: "Classical mechanics" },
      { key: "electromagnetism", label: "Electromagnetism" },
      { key: "quantum", label: "Quantum" },
      { key: "relativity", label: "Relativity" },
      { key: "thermo-stat-mech", label: "Thermo & stat mech" },
      { key: "condensed-matter", label: "Condensed matter" },
      { key: "particle-hep", label: "Particle / HEP" },
      { key: "astro-cosmo", label: "Astro & cosmology" },
      { key: "fluids", label: "Fluids" },
    ],
  },
  {
    key: "mathematics",
    label: "Mathematics",
    subareas: [
      { key: "calculus-analysis", label: "Calculus & analysis" },
      { key: "linear-algebra", label: "Linear algebra" },
      { key: "odes-pdes", label: "ODEs & PDEs" },
      { key: "probability-stats", label: "Probability & stats" },
      { key: "discrete-algebra", label: "Discrete & algebra" },
      { key: "geometry-topology", label: "Geometry & topology" },
      { key: "numerical-applied", label: "Numerical & applied" },
    ],
  },
  {
    key: "engineering",
    label: "Engineering",
    subareas: [
      { key: "mechanical", label: "Mechanical" },
      { key: "electrical", label: "Electrical" },
      { key: "civil", label: "Civil" },
      { key: "materials", label: "Materials" },
      { key: "chemical-eng", label: "Chemical" },
      { key: "software-eng", label: "Software" },
    ],
  },
  {
    key: "computation",
    label: "Computation",
    subareas: [
      { key: "algorithms-ds", label: "Algorithms & DS" },
      { key: "machine-learning", label: "Machine learning" },
      { key: "theory-of-computation", label: "Theory of computation" },
      { key: "systems", label: "Systems" },
      { key: "scientific-computing", label: "Scientific computing" },
      { key: "data-analysis", label: "Data analysis" },
    ],
  },
  {
    key: "biology",
    label: "Biology",
    subareas: [
      { key: "molecular-cell", label: "Molecular & cell" },
      { key: "neuroscience", label: "Neuroscience" },
      { key: "physiology", label: "Physiology" },
      { key: "ecology-evolution", label: "Ecology & evolution" },
      { key: "genomics", label: "Genomics" },
    ],
  },
  {
    key: "chemistry",
    label: "Chemistry",
    subareas: [
      { key: "organic", label: "Organic" },
      { key: "inorganic", label: "Inorganic" },
      { key: "physical-chem", label: "Physical" },
      { key: "analytical", label: "Analytical" },
      { key: "biochem", label: "Biochem" },
    ],
  },
] as const;

export const DOMAIN_BY_KEY: Record<DomainKey, DomainDef> = Object.fromEntries(
  DOMAINS.map((d) => [d.key, d]),
) as Record<DomainKey, DomainDef>;

export type RelationshipKey =
  | "studied_reconnecting"
  | "encounter_at_work"
  | "curious"
  | "follow_field";

export interface RelationshipCardDef {
  key: RelationshipKey;
  label: string;
  detail: string;
}

export const RELATIONSHIP_CARDS: ReadonlyArray<RelationshipCardDef> = [
  {
    key: "studied_reconnecting",
    label: "I studied this",
    detail: "and want to reconnect with it",
  },
  {
    key: "encounter_at_work",
    label: "I encounter this in my work",
    detail: "and want to go deeper",
  },
  {
    key: "curious",
    label: "I'm curious",
    detail: "and want to understand it better",
  },
  {
    key: "follow_field",
    label: "I follow this field",
    detail: "and want to engage more actively",
  },
] as const;

// Mapping from Stage 1 domain chip → database `nodes.domain` value (used by
// Stage 2 to foreground tiles and label them per the domain's relationship).
// Biology / chemistry chips have no corresponding foundation tiles yet — they
// flow through to Stage 3 ranking instead.
export const CHIP_TO_DB_DOMAIN: Partial<Record<DomainKey, string>> = {
  mathematics: "math",
  physics: "physics",
  engineering: "applied",
  computation: "applied",
};

const RELATIONSHIP_LABEL_BY_KEY: Record<RelationshipKey, string> = Object.fromEntries(
  RELATIONSHIP_CARDS.map((c) => [c.key, c.label]),
) as Record<RelationshipKey, string>;

// Build the per-domain payload the Python /survey/suggest-interests endpoint
// expects, expanding raw keys into human-readable labels so the Haiku rerank
// prompt can name the signals it sees.
export function buildDomainInputs(
  entries: ReadonlyArray<{ key: string; subareas: string[]; relationship: string | null }>,
): Array<{
  key: string;
  label: string;
  subareaLabels: string[];
  relationshipLabel: string | null;
}> {
  const out: Array<{
    key: string;
    label: string;
    subareaLabels: string[];
    relationshipLabel: string | null;
  }> = [];
  for (const e of entries) {
    const def = DOMAIN_BY_KEY[e.key as DomainKey];
    if (!def) continue;
    const subLabelByKey = new Map(def.subareas.map((s) => [s.key, s.label]));
    const subareaLabels = e.subareas
      .map((k) => subLabelByKey.get(k))
      .filter((l): l is string => Boolean(l));
    const relLabel =
      e.relationship && (e.relationship as RelationshipKey) in RELATIONSHIP_LABEL_BY_KEY
        ? RELATIONSHIP_LABEL_BY_KEY[e.relationship as RelationshipKey]
        : null;
    out.push({
      key: def.key,
      label: def.label,
      subareaLabels,
      relationshipLabel: relLabel,
    });
  }
  return out;
}
