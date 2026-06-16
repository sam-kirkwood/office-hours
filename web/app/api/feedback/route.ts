import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const VALID_CATEGORIES = new Set([
  "bug",
  "confusing_copy",
  "bad_problem_or_paper",
  "other",
]);

interface Body {
  url: string;
  category: string;
  body: string;
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let parsed: Body;
  try {
    parsed = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (!parsed.url?.trim()) {
    return NextResponse.json({ error: "url is required" }, { status: 400 });
  }
  if (!VALID_CATEGORIES.has(parsed.category)) {
    return NextResponse.json({ error: "Invalid category" }, { status: 400 });
  }
  if (!parsed.body?.trim()) {
    return NextResponse.json({ error: "body is required" }, { status: 400 });
  }

  const { error } = await supabase.from("feedback_reports").insert({
    user_id: user.id,
    url: parsed.url.trim(),
    category: parsed.category,
    body: parsed.body.trim(),
  });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
