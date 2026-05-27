import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { planQueue } from "@/lib/pythonApi";

// Cross-pollination accept endpoint.
//
// Standard "add interest from a raw text" goes through the add-interest dialog
// (web/components/addInterest/Dialog.tsx → /api/add-interest/parse +
// /api/add-interest/resolve) since the user is in the loop. This route is
// kept only for the cross-pollination card click on the daily view, where
// the node already exists in the megagraph and the user has just tapped
// "Add to my interests" on a surfaced suggestion. No dialog runs there —
// the canned intent_context is fine because the topic was surfaced from
// graph adjacency, not from a user's free-text expression.

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = (await request.json()) as {
      node_id?: string;
      added_via?: string;
    };

    if (body.added_via !== "cross_pollination" || !body.node_id) {
      return NextResponse.json(
        {
          error:
            "this endpoint accepts only cross_pollination adds; route raw-text adds through /api/add-interest/parse + /resolve",
        },
        { status: 400 },
      );
    }

    // intent_context is NOT NULL on user_interests (migration 20250018).
    const { error } = await supabase.from("user_interests").insert({
      user_id: user.id,
      node_id: body.node_id,
      weight: 1.0,
      added_via: "cross_pollination",
      intent_context: "Surfaced via cross-pollination from adjacent interests",
    });
    if (error) throw error;

    planQueue({ userId: user.id, triggeredBy: "manual" }).catch(() => null);

    return NextResponse.json({ ok: true, node_id: body.node_id });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
