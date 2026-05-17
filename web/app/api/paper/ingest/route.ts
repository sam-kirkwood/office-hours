import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { ingestPaper } from "@/lib/pythonApi";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await request.json()) as { raw_input?: string };
  const rawInput = body.raw_input?.trim();
  if (!rawInput) {
    return NextResponse.json({ error: "raw_input is required" }, { status: 400 });
  }

  const result = await ingestPaper({ userId: user.id, rawInput });
  return NextResponse.json(result);
}
