import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient } from "@/lib/surveyState";

// POST /api/profile/feedback
// Toggles a high-level feedback preference on user_preferences.
// Body: { key: <one of the allowlist>, active: boolean }
//   active=true  → upsert row with value="true"
//   active=false → delete row
// Read by the problem generator as soft biases on the three dials
// (survey-and-difficulty-design.md §3.5 + §6).

const FEEDBACK_KEYS = new Set([
  "feedback_too_hard",
  "feedback_assume_less",
  "feedback_more_papers",
  "feedback_harder_problems",
]);

interface Body {
  key: string;
  active: boolean;
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

  if (typeof body.key !== "string" || !FEEDBACK_KEYS.has(body.key)) {
    return NextResponse.json({ error: "Unknown feedback key" }, { status: 400 });
  }
  if (typeof body.active !== "boolean") {
    return NextResponse.json({ error: "active must be boolean" }, { status: 400 });
  }

  try {
    const admin = getAdminClient();
    if (body.active) {
      const { error } = await admin
        .from("user_preferences")
        .upsert(
          {
            user_id: user.id,
            key: body.key,
            value: "true",
            updated_at: new Date().toISOString(),
          },
          { onConflict: "user_id,key" },
        );
      if (error) throw error;
    } else {
      const { error } = await admin
        .from("user_preferences")
        .delete()
        .eq("user_id", user.id)
        .eq("key", body.key);
      if (error) throw error;
    }
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
