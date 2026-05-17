import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { assertAdminApi } from "@/lib/adminAuth";

export async function GET() {
  const err = await assertAdminApi();
  if (err) return err;

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data, error } = await supabaseAdmin
    .from("curation_proposals")
    .select("*")
    .order("proposed_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data ?? []);
}
