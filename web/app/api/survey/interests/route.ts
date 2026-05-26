import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";
import { parseAddInterest, resolveAddInterest } from "@/lib/pythonApi";

interface Body {
  // Slugs of Stage-3 suggestion tiles the user selected.
  selected_slugs: string[];
  // "Anything else?" free text — fed through the add-interest dialog.
  free_text: string;
}

// TODO(2d): replace this stub with the real Stage 4 (add-interest dialog) and
// Stage 5 (concept tour) UI. For now we run a best-guess server-side
// pass-through that calls /add-interest/parse → /resolve once per selected
// tile + once for the free text. The concept tour data returned from
// /resolve is discarded (Stage 5 surfaces it in the next session).
//
// This stub is what makes Stage 3 → Stage 6/7 functional end-to-end without
// the dialog UI being built yet.

async function bestGuessResolveOne(args: {
  userId: string;
  rawText: string;
  addedVia: "survey";
}): Promise<void> {
  const parsed = await parseAddInterest(args);
  for (const seg of parsed.segments) {
    const intentContext = seg.draft_intent_context || seg.mirror_back_md;
    const finalIntentText = seg.raw_text_segment || args.rawText;
    try {
      await resolveAddInterest({
        userId: args.userId,
        addedVia: args.addedVia,
        rawText: args.rawText,
        finalIntentText,
        intentContext,
        existingNodeSlug:
          seg.dedup.verdict === "same" ? seg.dedup.matched_node_slug : null,
        relatedNodeSlug:
          seg.dedup.verdict === "related" ? seg.dedup.matched_node_slug : null,
      });
    } catch (err) {
      console.error(
        `resolveAddInterest failed for segment "${seg.raw_text_segment}":`,
        err,
      );
    }
  }
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const selectedSlugs = (body.selected_slugs ?? []).filter((s) => typeof s === "string");
  const freeText = (body.free_text ?? "").trim();

  try {
    const admin = getAdminClient();

    await upsertSurveyStage(admin, user.id, "interests", {
      pending_interests_json: { tile_slugs: selectedSlugs, free_text: freeText },
    });

    // ----- Stage 4+5 stub: best-guess add-interest pass-through ------------
    // Resolve each selected tile by title (the safest stable signal we have).
    if (selectedSlugs.length > 0) {
      const { data: nodes } = await admin
        .from("nodes")
        .select("title, slug")
        .in("slug", selectedSlugs);

      for (const node of nodes ?? []) {
        await bestGuessResolveOne({
          userId: user.id,
          rawText: node.title as string,
          addedVia: "survey",
        });
      }
    }

    // Resolve the free-text input as a single add-interest call (the parser
    // will split it into multiple segments if appropriate).
    if (freeText.length > 0) {
      await bestGuessResolveOne({
        userId: user.id,
        rawText: freeText,
        addedVia: "survey",
      });
    }

    // Clear pending now that they're resolved into user_interests.
    await admin
      .from("surveys")
      .update({
        pending_interests_json: {},
        updated_at: new Date().toISOString(),
      })
      .eq("user_id", user.id);

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
