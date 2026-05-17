import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { assertAdminApi } from "@/lib/adminAuth";

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const err = await assertAdminApi();
  if (err) return err;

  const { id } = await params;

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { error } = await supabaseAdmin.from("queue_items").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
