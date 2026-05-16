import { redirect, notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import Link from "next/link";
import MarkdownLatex from "@/lib/markdown";
import type { NotebookEntry, Attempt, Problem, ProblemHint, Node } from "@/lib/types";

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/* Wrapper that applies consistent spacing and serif styling to markdown output */
function ReadingBlock({ source, className = "" }: { source: string; className?: string }) {
  return (
    <div
      className={`font-serif text-base leading-[1.7] text-foreground
        [&_p]:mb-4 [&_p:last-child]:mb-0
        [&_strong]:font-semibold [&_em]:italic
        [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol_li]:mb-1.5
        [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5 [&_ul_li]:mb-1.5
        [&_code]:font-mono [&_code]:text-sm [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
        [&_pre]:font-mono [&_pre]:text-sm [&_pre]:bg-muted [&_pre]:p-4 [&_pre]:rounded-md [&_pre]:overflow-x-auto [&_pre]:mb-4
        [&_blockquote]:border-l-2 [&_blockquote]:border-amber [&_blockquote]:pl-4 [&_blockquote]:text-muted-foreground [&_blockquote]:mb-4
        ${className}`}
    >
      <MarkdownLatex source={source} />
    </div>
  );
}

export default async function NotebookEntryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: entry } = await adminClient
    .from("notebook_entries")
    .select("id, user_id, entry_kind, ref_id, title, topic_node_slugs, created_at, updated_at")
    .eq("id", id)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!entry) notFound();

  if (entry.entry_kind === "paper_engagement") {
    return (
      <div className="mx-auto max-w-2xl px-5 py-12">
        <Link href="/notebook" className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]">
          ← Notebook
        </Link>
        <h1 className="mt-8 text-xl font-semibold text-foreground">{entry.title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">Paper engagement — coming in Phase 6-rev.</p>
      </div>
    );
  }

  // problem_attempt
  const { data: attempt } = await adminClient
    .from("attempts")
    .select(
      "id, problem_id, hint_levels_used, parsed_markdown, user_edited_markdown, grade_response_md, submitted_at",
    )
    .eq("id", entry.ref_id)
    .maybeSingle();

  if (!attempt) notFound();

  const { data: problem } = await adminClient
    .from("problems")
    .select("id, topic_node_id, statement_md, context_md, difficulty")
    .eq("id", (attempt as Attempt).problem_id)
    .maybeSingle();

  const { data: hints } = await adminClient
    .from("problem_hints")
    .select("id, level, text")
    .eq("problem_id", (attempt as Attempt).problem_id)
    .order("level", { ascending: true });

  let node: Node | null = null;
  if ((problem as Problem | null)?.topic_node_id) {
    const { data: nodeRow } = await adminClient
      .from("nodes")
      .select("id, slug, title, domain, difficulty_hint")
      .eq("id", (problem as Problem).topic_node_id!)
      .maybeSingle();
    node = nodeRow as Node | null;
  }

  const hintLevelsUsed = new Set<number>((attempt as Attempt).hint_levels_used ?? []);
  const openedHints = ((hints ?? []) as ProblemHint[]).filter((h) => hintLevelsUsed.has(h.level));
  const displaySolution =
    (attempt as Attempt).user_edited_markdown ?? (attempt as Attempt).parsed_markdown;

  return (
    <div className="mx-auto max-w-2xl px-5 py-12">

      {/* Back link */}
      <Link
        href="/notebook"
        className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
      >
        ← Notebook
      </Link>

      {/* Meta + title */}
      <div className="mt-8 mb-10">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {node && (
            <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              {node.slug.replace(/-/g, "‑")}
            </span>
          )}
          {node && <span className="text-muted-foreground/40">·</span>}
          <span className="text-xs text-muted-foreground">{fmt(entry.created_at)}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{entry.title}</h1>
      </div>

      {/* Problem statement */}
      <section className="mb-12">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Problem
        </h2>
        <ReadingBlock source={(problem as Problem | null)?.statement_md ?? ""} />
      </section>

      {/* Context */}
      {(problem as Problem | null)?.context_md && (
        <section className="mb-12">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Context
          </h2>
          <div className="border-l-2 border-amber pl-5">
            <ReadingBlock
              source={(problem as Problem).context_md!}
              className="text-sm text-muted-foreground"
            />
          </div>
        </section>
      )}

      {/* Hints opened */}
      <section className="mb-12">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Hints you opened
        </h2>
        {openedHints.length === 0 ? (
          <p className="text-sm text-muted-foreground">None</p>
        ) : (
          <div className="space-y-2">
            {openedHints.map((h) => (
              <div key={h.level} className="rounded-md border border-border px-4 py-3">
                <span className="mr-2 text-xs font-semibold text-muted-foreground">
                  Hint {h.level}.
                </span>
                <span className="font-serif text-sm leading-relaxed text-foreground">{h.text}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Solution */}
      {displaySolution && (
        <section className="mb-12">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Your solution
          </h2>
          <div className="rounded-md border border-border bg-card px-5 py-5">
            <ReadingBlock source={displaySolution} />
          </div>
        </section>
      )}

      {/* Feedback */}
      {(attempt as Attempt).grade_response_md && (
        <section className="mb-12">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Feedback
          </h2>
          <div className="border-l-2 border-amber pl-5">
            <ReadingBlock
              source={(attempt as Attempt).grade_response_md!}
              className="text-sm text-muted-foreground"
            />
          </div>
        </section>
      )}

    </div>
  );
}
