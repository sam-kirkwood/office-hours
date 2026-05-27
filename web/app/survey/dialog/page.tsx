import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import {
  gateFor,
  getAdminClient,
  loadSurveyDraft,
} from "@/lib/surveyState";
import DialogOrchestrator from "@/components/survey/DialogOrchestrator";

// Stage 4 + 5 host. The orchestrator walks the user through the add-interest
// dialog + concept tour for every interest from Stage 3 (the tile slugs and
// free text saved on surveys.pending_interests_json). When it finishes it
// marks the `dialog` stage complete and routes to /survey/balance.

export default async function DialogPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const admin = getAdminClient();
  const draft = await loadSurveyDraft(admin, user.id);
  const gate = gateFor("dialog", draft.completed_stages);
  if (gate === "done") redirect("/daily");
  if (gate !== null) redirect(`/survey/${gate}`);

  const pending = draft.pending_interests_json ?? {};
  const tileSlugs = pending.tile_slugs ?? [];
  const freeText = (pending.free_text ?? "").trim();

  // Resolve tile slugs back to their titles so each tile becomes one raw_text
  // input. /add-interest/parse will re-dedup against the megagraph.
  const inputs: string[] = [];
  if (tileSlugs.length > 0) {
    const { data: nodes } = await admin
      .from("nodes")
      .select("title, slug")
      .in("slug", tileSlugs);
    const bySlug = new Map<string, string>();
    for (const n of nodes ?? []) {
      bySlug.set(n.slug as string, n.title as string);
    }
    // Preserve user pick order.
    for (const slug of tileSlugs) {
      const title = bySlug.get(slug);
      if (title) inputs.push(title);
    }
  }
  if (freeText.length > 0) inputs.push(freeText);

  return <DialogOrchestrator inputs={inputs} />;
}
