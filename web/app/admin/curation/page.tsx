import { createClient } from "@supabase/supabase-js";
import { requireAdmin } from "@/lib/adminAuth";
import { describeProposal } from "@/lib/describeProposal";
import type { CurationProposal } from "@/lib/describeProposal";
import { Badge } from "@/components/ui/badge";
import { RunReportButton, DecideButton, ApplyButton } from "@/components/CurationActions";

function kindBadgeClass(kind: string): string {
  switch (kind) {
    case "merge":
    case "split":
      return "border-amber/60 text-amber bg-transparent";
    case "rename":
    case "add_edge":
      return "border-[var(--forest)] text-[var(--forest)] bg-transparent";
    case "promote":
    case "demote":
      return "bg-[var(--amber-subtle)] text-amber border-amber/30";
    case "deprecate":
      return "border-destructive text-destructive bg-transparent";
    default:
      return "";
  }
}

function ProposalCard({
  proposal,
  showDecide,
}: {
  proposal: CurationProposal;
  showDecide: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-3">
        <Badge
          variant="outline"
          className={`text-[10px] uppercase tracking-widest ${kindBadgeClass(proposal.kind)}`}
        >
          {proposal.kind}
        </Badge>
        <span className="text-sm font-medium text-foreground">
          {describeProposal(proposal)}
        </span>
      </div>
      {typeof proposal.payload_json.rationale === "string" && (
        <p className="mb-3 font-serif text-sm text-muted-foreground">
          {proposal.payload_json.rationale}
        </p>
      )}
      {showDecide && (
        <div className="flex gap-2">
          <DecideButton proposalId={proposal.id} action="approve" />
          <DecideButton proposalId={proposal.id} action="reject" />
        </div>
      )}
    </div>
  );
}

export default async function CurationPage() {
  await requireAdmin();

  const supabaseAdmin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: proposals } = await supabaseAdmin
    .from("curation_proposals")
    .select("*")
    .order("proposed_at", { ascending: false });

  const allProposals = (proposals ?? []) as CurationProposal[];
  const pending = allProposals.filter((p) => p.status === "pending");
  const approved = allProposals.filter((p) => p.status === "approved");
  const rejected = allProposals.filter((p) => p.status === "rejected");
  const applied = allProposals.filter((p) => p.status === "applied");

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Curation proposals</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Review and act on the megagraph maintenance suggestions.
          </p>
        </div>
        <RunReportButton />
      </div>

      {/* Pending */}
      <section className="mb-10">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Pending ({pending.length})
        </h2>
        {pending.length === 0 ? (
          <p className="text-sm text-muted-foreground">No pending proposals.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {pending.map((p) => (
              <ProposalCard key={p.id} proposal={p} showDecide />
            ))}
          </div>
        )}
      </section>

      {/* Approved */}
      <section className="mb-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Approved — ready to apply ({approved.length})
          </h2>
          <ApplyButton count={approved.length} />
        </div>
        {approved.length === 0 ? (
          <p className="text-sm text-muted-foreground">No approved proposals.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {approved.map((p) => (
              <ProposalCard key={p.id} proposal={p} showDecide={false} />
            ))}
          </div>
        )}
      </section>

      {/* Applied */}
      {applied.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Applied ({applied.length})
          </h2>
          <div className="flex flex-col gap-3">
            {applied.map((p) => (
              <ProposalCard key={p.id} proposal={p} showDecide={false} />
            ))}
          </div>
        </section>
      )}

      {/* Rejected */}
      {rejected.length > 0 && (
        <section>
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Rejected ({rejected.length})
          </h2>
          <div className="flex flex-col gap-3">
            {rejected.map((p) => (
              <ProposalCard key={p.id} proposal={p} showDecide={false} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
