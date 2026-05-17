import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { assertAdminApi } from "@/lib/adminAuth";
import {
  validateNodeIds,
  applyMerge,
  applySplit,
  applyRename,
  applyPromote,
  applyDemote,
  applyAddEdge,
  applyDeprecate,
} from "@/lib/applyProposal";

export async function POST() {
  const err = await assertAdminApi();
  if (err) return err;

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: proposals, error: loadErr } = await supabaseAdmin
    .from("curation_proposals")
    .select("*")
    .eq("status", "approved");

  if (loadErr) {
    return NextResponse.json({ error: loadErr.message }, { status: 500 });
  }

  let appliedCount = 0;
  const now = new Date().toISOString();
  const adminEmail = process.env.ADMIN_EMAIL ?? "operator";

  for (const proposal of proposals ?? []) {
    const payload = proposal.payload_json as Record<string, unknown>;

    // Validate node IDs before mutating anything
    const { valid, missingIds } = await validateNodeIds(supabaseAdmin, proposal.kind, payload);
    if (!valid) {
      console.warn(
        `Proposal ${proposal.id} skipped: missing node IDs [${missingIds.join(", ")}]`,
      );
      await supabaseAdmin
        .from("curation_proposals")
        .update({
          status: "rejected",
          decided_at: now,
          decided_by: `system: Invalid node_id (${missingIds.join(", ")})`,
        })
        .eq("id", proposal.id);
      continue;
    }

    try {
      switch (proposal.kind) {
        case "merge":
          await applyMerge(supabaseAdmin, payload);
          break;
        case "split":
          await applySplit(supabaseAdmin, payload);
          break;
        case "rename":
          await applyRename(supabaseAdmin, payload);
          break;
        case "promote":
          await applyPromote(supabaseAdmin, payload);
          break;
        case "demote":
          await applyDemote(supabaseAdmin, payload);
          break;
        case "add_edge":
          await applyAddEdge(supabaseAdmin, payload);
          break;
        case "deprecate":
          await applyDeprecate(supabaseAdmin, payload);
          break;
        default:
          console.warn(`Unknown proposal kind: ${proposal.kind} — skipping`);
          continue;
      }

      await supabaseAdmin
        .from("curation_proposals")
        .update({ status: "applied", decided_at: now, decided_by: adminEmail })
        .eq("id", proposal.id);

      appliedCount++;
    } catch (e) {
      console.error(`Failed to apply proposal ${proposal.id} (${proposal.kind}):`, e);
    }
  }

  // Write system snapshot to unlock cross-pollination gate
  const [{ data: nodes }, { data: edges }] = await Promise.all([
    supabaseAdmin.from("nodes").select("id, slug, title, kind, domain, pool_status"),
    supabaseAdmin
      .from("edges")
      .select("id, source_node_id, target_node_id, edge_kind, weight"),
  ]);

  const takenAt = new Date().toISOString();
  const snapshotJson = {
    version: 1,
    taken_at: takenAt,
    nodes: nodes ?? [],
    edges: edges ?? [],
  };

  const { data: snap, error: snapErr } = await supabaseAdmin
    .from("megagraph_snapshots")
    .insert({
      label: `curation-${takenAt.slice(0, 10)}`,
      snapshot_json: snapshotJson,
      taken_by: "system",
      taken_at: takenAt,
    })
    .select("id")
    .single();

  if (snapErr) {
    return NextResponse.json({ error: `Snapshot failed: ${snapErr.message}` }, { status: 500 });
  }

  return NextResponse.json({ applied_count: appliedCount, snapshot_id: snap.id });
}
