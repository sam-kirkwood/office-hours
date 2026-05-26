import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import FoundationsGrid from "@/components/survey/FoundationsGrid";
import { CHIP_TO_DB_DOMAIN, type DomainKey } from "@/lib/surveyDomains";
import type { Node } from "@/lib/types";

export default async function FoundationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const gate = gateFor("foundations", draft.completed_stages);
  if (gate === "done") redirect("/daily");
  if (gate !== null) redirect(`/survey/${gate}`);

  const { data: nodes } = await admin
    .from("nodes")
    .select(
      "id, slug, title, description_md, domain, kind, difficulty_hint, subtopics_json, pool_status, created_at",
    )
    .eq("kind", "foundation")
    .eq("pool_status", "active");

  const foundationNodes = (nodes ?? []) as Node[];
  const initialRefreshSlugs = Object.entries(draft.node_ratings_json)
    .filter(([, v]) => v === "refresh")
    .map(([slug]) => slug);

  // Build per-db-domain relationship lookup from the Stage 1 domain entries.
  // Multiple chips can map to the same db domain (engineering, computation →
  // applied) — first-wins.
  const relationshipByDomain: Record<string, string | null> = {
    math: null,
    physics: null,
    applied: null,
  };
  for (const entry of draft.background_json.domains) {
    const db = CHIP_TO_DB_DOMAIN[entry.key as DomainKey];
    if (!db) continue;
    if (relationshipByDomain[db] == null && entry.relationship) {
      relationshipByDomain[db] = entry.relationship;
    }
  }

  const foregroundDomains = Array.from(
    new Set(
      draft.background_json.domains
        .map((d) => CHIP_TO_DB_DOMAIN[d.key as DomainKey])
        .filter((d): d is string => Boolean(d)),
    ),
  );

  return (
    <FoundationsGrid
      foundationNodes={foundationNodes}
      initialRefreshSlugs={initialRefreshSlugs}
      relationshipByDomain={relationshipByDomain}
      foregroundDomains={foregroundDomains}
    />
  );
}
