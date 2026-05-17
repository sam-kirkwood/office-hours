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

  const [
    { data: nodes, error: nodesError },
    { data: edges, error: edgesError },
    { data: snapshots, error: snapshotsError },
    { data: proposals, error: proposalsError },
  ] = await Promise.all([
    supabaseAdmin.from("nodes").select("id, slug, title, kind, domain, pool_status"),
    supabaseAdmin.from("edges").select("id, source_node_id, target_node_id, edge_kind, weight"),
    supabaseAdmin
      .from("megagraph_snapshots")
      .select("id, label, taken_at, taken_by")
      .order("taken_at", { ascending: true }),
    supabaseAdmin
      .from("curation_proposals")
      .select("*")
      .eq("status", "pending"),
  ]);

  const error = nodesError ?? edgesError ?? snapshotsError ?? proposalsError;
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    nodes: nodes ?? [],
    edges: edges ?? [],
    snapshots: snapshots ?? [],
    pending_proposals: proposals ?? [],
  });
}
