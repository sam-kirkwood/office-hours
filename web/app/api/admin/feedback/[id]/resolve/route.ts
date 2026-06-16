import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { assertAdminApi } from "@/lib/adminAuth";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const err = await assertAdminApi();
  if (err) return err;

  const { id } = await params;

  const admin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { error } = await admin
    .from("feedback_reports")
    .update({ resolved_at: new Date().toISOString() })
    .eq("id", id)
    .is("resolved_at", null);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
