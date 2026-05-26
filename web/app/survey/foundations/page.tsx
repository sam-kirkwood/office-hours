import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import FoundationsGrid from "@/components/survey/FoundationsGrid";
import type { Node } from "@/lib/types";

// Stage 1 chips → database `nodes.domain` mapping. Chips outside math/physics
// don't directly foreground anything in Stage 2 (those domains have no
// foundation nodes yet); they still flow into the Stage 3 suggestion ranking.
const CHIP_TO_DOMAIN: Record<string, string> = {
  physics: "physics",
  mathematics: "math",
};

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

  const chips = draft.background_json?.domain_chips ?? [];
  const foregroundDomains = Array.from(
    new Set(chips.map((c) => CHIP_TO_DOMAIN[c]).filter((d): d is string => Boolean(d))),
  );

  return (
    <FoundationsGrid
      foundationNodes={foundationNodes}
      initialRefreshSlugs={initialRefreshSlugs}
      relationshipCards={draft.background_json?.relationship_cards ?? []}
      foregroundDomains={foregroundDomains}
    />
  );
}
