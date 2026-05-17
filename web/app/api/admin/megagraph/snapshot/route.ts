import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { assertAdminApi } from "@/lib/adminAuth";

export async function POST() {
  const err = await assertAdminApi();
  if (err) return err;

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const [{ data: nodes }, { data: edges }] = await Promise.all([
    supabaseAdmin.from("nodes").select("id, slug, title, kind, domain, pool_status"),
    supabaseAdmin.from("edges").select("id, source_node_id, target_node_id, edge_kind, weight"),
  ]);

  const takenAt = new Date().toISOString();
  const snapshotJson = {
    version: 1,
    taken_at: takenAt,
    nodes: nodes ?? [],
    edges: edges ?? [],
  };

  const label = `operator-${takenAt.slice(0, 10)}`;

  const { data, error } = await supabaseAdmin
    .from("megagraph_snapshots")
    .insert({
      label,
      snapshot_json: snapshotJson,
      taken_by: "operator",
      taken_at: takenAt,
    })
    .select("id, label, taken_at")
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
