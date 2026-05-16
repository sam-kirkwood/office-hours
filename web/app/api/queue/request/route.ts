import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { addInterest, generateProblem } from "@/lib/pythonApi";

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { node_id } = await request.json();
  if (!node_id) return NextResponse.json({ error: "node_id required" }, { status: 400 });

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  // Check if this node is already in user_interests
  const { data: existing } = await adminClient
    .from("user_interests")
    .select("id")
    .eq("user_id", user.id)
    .eq("node_id", node_id)
    .maybeSingle();

  if (!existing) {
    // Load node title for addInterest
    const { data: node } = await adminClient
      .from("nodes")
      .select("title")
      .eq("id", node_id)
      .maybeSingle();

    if (!node) return NextResponse.json({ error: "Node not found" }, { status: 404 });

    await addInterest({ userId: user.id, rawText: node.title, addedVia: "explicit_request" });
  }

  const result = await generateProblem({ userId: user.id, nodeId: node_id });

  return NextResponse.json({ queue_item_id: result.queue_item_id });
}
