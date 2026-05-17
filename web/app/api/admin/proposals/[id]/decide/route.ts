import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";
import { assertAdminApi } from "@/lib/adminAuth";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const err = await assertAdminApi();
  if (err) return err;

  const { id } = await params;
  const body = await req.json();
  const action: "approve" | "reject" = body.action;

  if (action !== "approve" && action !== "reject") {
    return NextResponse.json({ error: "action must be approve or reject" }, { status: 400 });
  }

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const newStatus = action === "approve" ? "approved" : "rejected";

  const { error } = await supabaseAdmin
    .from("curation_proposals")
    .update({
      status: newStatus,
      decided_at: new Date().toISOString(),
      decided_by: process.env.ADMIN_EMAIL,
    })
    .eq("id", id);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true, status: newStatus });
}
