import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { addInterest } from "@/lib/pythonApi";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const { raw_text } = (await request.json()) as { raw_text: string };
    if (!raw_text?.trim()) {
      return NextResponse.json({ error: "raw_text is required" }, { status: 400 });
    }

    const result = await addInterest({
      userId: user.id,
      rawText: raw_text.trim(),
      addedVia: "explicit_request",
    });

    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
