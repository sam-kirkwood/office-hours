import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient } from "@/lib/surveyState";

// DELETE /api/interest/[node_id]
// Removes the user_interests row for this user + node. The node itself stays
// in the megagraph and is still available to other users
// (survey-and-difficulty-design.md §1.8.2).

export async function DELETE(
  _request: Request,
  context: { params: Promise<{ node_id: string }> },
) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { node_id } = await context.params;
  if (!node_id) {
    return NextResponse.json({ error: "node_id required" }, { status: 400 });
  }

  try {
    const admin = getAdminClient();
    const { error } = await admin
      .from("user_interests")
      .delete()
      .eq("user_id", user.id)
      .eq("node_id", node_id);
    if (error) throw error;
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
