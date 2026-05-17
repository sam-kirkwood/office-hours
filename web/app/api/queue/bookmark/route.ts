import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const { queue_item_id } = (await request.json()) as { queue_item_id: string };
    if (!queue_item_id?.trim()) {
      return NextResponse.json({ error: "queue_item_id is required" }, { status: 400 });
    }

    const { error } = await supabase
      .from("queue_items")
      .update({ state: "dismissed" })
      .eq("id", queue_item_id)
      .eq("user_id", user.id);

    if (error) throw error;

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
