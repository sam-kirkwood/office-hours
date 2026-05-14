import { createClient as createServerClient } from "@/lib/supabase/server";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export async function POST() {
  try {
    const supabase = await createServerClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

    if (!process.env.SUPABASE_SECRET_KEY) {
      return NextResponse.json({ error: "SUPABASE_SECRET_KEY not set" }, { status: 500 });
    }

    const adminClient = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SECRET_KEY
    );

    const { data: plan } = await adminClient
      .from("user_plans")
      .select("id")
      .eq("user_id", user.id)
      .eq("status", "pending_review")
      .maybeSingle();

    if (!plan) {
      return NextResponse.json({ error: "No pending plan found" }, { status: 404 });
    }

    await adminClient.from("user_plans").update({ status: "active" }).eq("id", plan.id);

    // Activate the first pending node
    const { data: firstNode } = await adminClient
      .from("plan_nodes")
      .select("id")
      .eq("plan_id", plan.id)
      .eq("state", "pending")
      .order("order_index")
      .limit(1)
      .maybeSingle();

    if (firstNode) {
      await adminClient.from("plan_nodes").update({ state: "active" }).eq("id", firstNode.id);
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
