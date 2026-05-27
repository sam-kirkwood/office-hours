import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { resolveAddInterest } from "@/lib/pythonApi";

// Thin proxy to the Python /add-interest/resolve endpoint. The Python service
// writes the user_interests row and, when needed, generates a new node.

interface Body {
  added_via: "survey" | "explicit_request" | "cross_pollination";
  raw_text: string;
  final_intent_text: string;
  intent_context: string;
  existing_node_slug?: string | null;
  related_node_slug?: string | null;
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

  if (!body.raw_text || !body.final_intent_text || !body.intent_context) {
    return NextResponse.json(
      { error: "raw_text, final_intent_text, intent_context are required" },
      { status: 400 },
    );
  }

  try {
    const data = await resolveAddInterest({
      userId: user.id,
      addedVia: body.added_via ?? "explicit_request",
      rawText: body.raw_text,
      finalIntentText: body.final_intent_text,
      intentContext: body.intent_context,
      existingNodeSlug: body.existing_node_slug ?? null,
      relatedNodeSlug: body.related_node_slug ?? null,
    });
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
