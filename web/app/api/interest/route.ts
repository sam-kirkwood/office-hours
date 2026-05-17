import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { addInterest, proposePapers, updateQueue } from "@/lib/pythonApi";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const body = (await request.json()) as {
      raw_text?: string;
      node_id?: string;
      added_via?: string;
    };

    // Cross-pollination path: node already exists in the megagraph; skip dedup/generate.
    if (body.added_via === "cross_pollination" && body.node_id) {
      const { error } = await supabase.from("user_interests").insert({
        user_id: user.id,
        node_id: body.node_id,
        weight: 1.0,
        added_via: "cross_pollination",
      });
      if (error) throw error;

      updateQueue({ userId: user.id, trigger: "interest_add" }).catch(() => null);

      return NextResponse.json({ ok: true, node_id: body.node_id });
    }

    // Standard path: resolve raw_text via the Python /add-interest route.
    const { raw_text } = body;
    if (!raw_text?.trim()) {
      return NextResponse.json({ error: "raw_text is required" }, { status: 400 });
    }

    const result = await addInterest({
      userId: user.id,
      rawText: raw_text.trim(),
      addedVia: "explicit_request",
    });

    proposePapers({ userId: user.id }).catch(() => null);
    updateQueue({ userId: user.id, trigger: "interest_add" }).catch(() => null);

    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
