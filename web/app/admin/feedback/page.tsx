import { createClient } from "@supabase/supabase-js";
import { requireAdmin } from "@/lib/adminAuth";
import { Badge } from "@/components/ui/badge";
import { FeedbackResolveButton } from "@/components/FeedbackActions";

interface FeedbackReport {
  id: string;
  user_id: string;
  url: string;
  category: string;
  body: string;
  created_at: string;
  resolved_at: string | null;
  profiles: { email: string | null }[] | null;
}

function categoryLabel(cat: string): string {
  switch (cat) {
    case "bug":
      return "Bug";
    case "confusing_copy":
      return "Confusing copy";
    case "bad_problem_or_paper":
      return "Bad problem or paper";
    default:
      return "Other";
  }
}

function categoryBadgeClass(cat: string): string {
  switch (cat) {
    case "bug":
      return "border-destructive text-destructive bg-transparent";
    case "confusing_copy":
      return "border-amber/60 text-amber bg-transparent";
    case "bad_problem_or_paper":
      return "border-[var(--forest)] text-[var(--forest)] bg-transparent";
    default:
      return "";
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function urlPath(raw: string): string {
  try {
    return new URL(raw).pathname;
  } catch {
    return raw;
  }
}

function ReportCard({ report }: { report: FeedbackReport }) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge
          variant="outline"
          className={`text-[10px] uppercase tracking-widest ${categoryBadgeClass(report.category)}`}
        >
          {categoryLabel(report.category)}
        </Badge>
        <span>{report.profiles?.[0]?.email ?? "(unknown)"}</span>
        <span>·</span>
        <span>{formatDate(report.created_at)}</span>
        <span>·</span>
        <span className="font-mono text-[11px]">{urlPath(report.url)}</span>
      </div>
      <p className="mb-3 font-serif text-sm text-foreground">{report.body}</p>
      {report.resolved_at ? (
        <span className="text-xs text-muted-foreground">
          Resolved {formatDate(report.resolved_at)}
        </span>
      ) : (
        <FeedbackResolveButton id={report.id} />
      )}
    </div>
  );
}

export default async function FeedbackPage() {
  await requireAdmin();

  const admin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: reports } = await admin
    .from("feedback_reports")
    .select("id, user_id, url, category, body, created_at, resolved_at, profiles(email)")
    .order("resolved_at", { ascending: false, nullsFirst: true })
    .order("created_at", { ascending: false });

  const rows = (reports ?? []) as unknown as FeedbackReport[];
  const unresolved = rows.filter((r) => !r.resolved_at);
  const resolved = rows.filter((r) => r.resolved_at);
  const total = rows.length;

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8">
        <h1 className="text-lg font-semibold text-foreground">Feedback</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {total} report{total !== 1 ? "s" : ""} total · {unresolved.length} unresolved
        </p>
      </div>

      {total === 0 && (
        <p className="text-sm text-muted-foreground">No feedback yet.</p>
      )}

      {unresolved.length > 0 && (
        <div className="flex flex-col gap-3">
          {unresolved.map((r) => (
            <ReportCard key={r.id} report={r} />
          ))}
        </div>
      )}

      {resolved.length > 0 && (
        <details className="mt-8 open:pb-2">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground">
            Resolved ({resolved.length})
          </summary>
          <div className="mt-4 flex flex-col gap-3">
            {resolved.map((r) => (
              <ReportCard key={r.id} report={r} />
            ))}
          </div>
        </details>
      )}
    </main>
  );
}
