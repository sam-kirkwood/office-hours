import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: nodeId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: existing } = await adminClient
    .from("bookmarks")
    .select("id")
    .eq("user_id", user.id)
    .eq("kind", "node")
    .eq("ref_id_or_text", nodeId)
    .maybeSingle();

  if (existing) {
    await adminClient.from("bookmarks").delete().eq("id", existing.id);
    return NextResponse.json({ bookmarked: false });
  }

  await adminClient.from("bookmarks").insert({
    user_id: user.id,
    kind: "node",
    ref_id_or_text: nodeId,
  });

  return NextResponse.json({ bookmarked: true });
}
