export interface CurationProposal {
  id: string;
  kind: string;
  payload_json: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "applied";
  proposed_at: string;
  decided_at: string | null;
  decided_by: string | null;
}

export function describeProposal(proposal: CurationProposal): string {
  const p = proposal.payload_json as Record<string, string>;
  switch (proposal.kind) {
    case "merge":
      return `Merge "${p.source_title}" into "${p.target_title}"`;
    case "split":
      return `Split "${p.source_title}" — create "${p.new_node_title}"`;
    case "rename":
      return `Rename "${p.old_title}" → "${p.new_title}" (slug: ${p.new_slug})`;
    case "promote":
      return `Promote "${p.title}" from interest → foundation`;
    case "demote":
      return `Demote "${p.title}" from foundation → interest`;
    case "add_edge":
      return `Add ${p.edge_kind} edge: "${p.source_title}" → "${p.target_title}" (weight ${p.weight})`;
    case "deprecate":
      return `Deprecate "${p.title}"`;
    default:
      return `Unknown proposal kind: ${proposal.kind}`;
  }
}
