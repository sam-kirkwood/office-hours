import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { parseAddInterest } from "@/lib/pythonApi";

// Thin proxy to the Python /add-interest/parse endpoint. Auth-checked; the
// Python side requires the internal bearer token which is set by pythonPost.
//
// Used by: Stage 4 onboarding orchestrator, the daily-tab RequestBox (for §2.7
// case detection), and any other client-side caller that needs to surface the
// dialog. Read-only — never writes to the database.

interface Body {
  raw_text: string;
  added_via: "survey" | "explicit_request" | "cross_pollination";
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

  const rawText = (body.raw_text ?? "").trim();
  if (!rawText) {
    return NextResponse.json({ error: "raw_text required" }, { status: 400 });
  }
  const addedVia = body.added_via ?? "explicit_request";

  try {
    const data = await parseAddInterest({
      userId: user.id,
      rawText,
      addedVia,
    });
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
