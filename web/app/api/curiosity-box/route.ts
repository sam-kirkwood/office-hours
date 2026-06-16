// POST /api/curiosity-box — thin auth wrapper over the Python /curiosity-box
// classify-and-route endpoint (§A4).
//
// The Python side handles all classification and dispatching; this route only
// adds Supabase auth so the client never talks to Python directly.

import { createClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";
import { handleCuriosityBox } from "@/lib/pythonApi";

export async function POST(req: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: { raw_text?: string };
  try {
    body = (await req.json()) as { raw_text?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const rawText = (body.raw_text ?? "").trim();
  if (!rawText) {
    return NextResponse.json({ error: "raw_text required" }, { status: 400 });
  }

  try {
    const result = await handleCuriosityBox({ userId: user.id, rawText });
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
