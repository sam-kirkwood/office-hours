import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import BackgroundForm from "@/components/survey/BackgroundForm";
import {
  DOMAIN_BY_KEY,
  RELATIONSHIP_CARDS,
  type DomainKey,
  type RelationshipKey,
} from "@/lib/surveyDomains";

const VALID_RELS = new Set<string>(RELATIONSHIP_CARDS.map((c) => c.key));

export default async function BackgroundPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const gate = gateFor("background", draft.completed_stages);
  if (gate === "done") redirect("/daily");
  if (gate !== null) redirect(`/survey/${gate}`);

  // Filter draft entries against the canonical chip + relationship sets in
  // case stored data drifts from the typed shape.
  const initialDomains = (draft.background_json.domains ?? [])
    .filter((d) => DOMAIN_BY_KEY[d.key as DomainKey])
    .map((d) => {
      const def = DOMAIN_BY_KEY[d.key as DomainKey];
      const validSubs = new Set(def.subareas.map((s) => s.key));
      return {
        key: d.key as DomainKey,
        subareas: d.subareas.filter((s) => validSubs.has(s)),
        relationship:
          d.relationship && VALID_RELS.has(d.relationship)
            ? (d.relationship as RelationshipKey)
            : null,
      };
    });

  return (
    <BackgroundForm
      initialDomains={initialDomains}
      initialShortText={draft.free_text_intent ?? ""}
    />
  );
}
