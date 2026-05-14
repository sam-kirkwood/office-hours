import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { ensureTodaysAssignment } from "@/lib/dailyAssignment";
import MarkdownLatex from "@/lib/markdown";

export default async function DailyPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const result = await ensureTodaysAssignment(user.id);

  if (result.kind === "no_plan") redirect("/plan");

  if (result.kind === "plan_complete") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <p className="mb-3 text-3xl">🎉</p>
        <h1 className="mb-2 text-xl font-semibold text-zinc-900">
          You&apos;ve worked through your plan.
        </h1>
        <p className="mb-6 text-sm text-zinc-500">
          Add new topics or rebuild your plan to keep going.
        </p>
        <Link
          href="/survey"
          className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700"
        >
          Extend your plan
        </Link>
      </div>
    );
  }

  const { problem, hints, contextHook } = result.bundle;
  const contextMd = contextHook?.summary_md ?? problem.generated_context_md;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      {contextMd && (
        <div className="mb-8 rounded-xl bg-amber-50 px-5 py-4 text-sm text-amber-900 ring-1 ring-amber-200">
          <p className="mb-1 font-semibold">
            {contextHook ? contextHook.title : "Historical context"}
          </p>
          <MarkdownLatex source={contextMd} className="prose prose-sm prose-amber" />
        </div>
      )}

      <h1 className="mb-4 text-xl font-semibold text-zinc-900">
        Today&apos;s Problem
      </h1>
      <div className="mb-6 rounded-xl bg-white px-5 py-4 text-zinc-800 ring-1 ring-zinc-200">
        <MarkdownLatex source={problem.statement_md} className="prose prose-zinc" />
      </div>

      <details className="mb-8 rounded-xl ring-1 ring-zinc-200">
        <summary className="cursor-pointer rounded-xl px-5 py-3 text-sm font-medium text-zinc-600 hover:bg-zinc-50 select-none">
          Show hints
        </summary>
        <ol className="divide-y divide-zinc-100 px-5 pb-2 pt-1">
          {hints.map((hint) => (
            <li key={hint.id} className="py-3 text-sm text-zinc-700">
              <span className="mr-2 font-semibold text-zinc-400">
                Hint {hint.level}
              </span>
              <MarkdownLatex source={hint.text} className="prose prose-sm prose-zinc inline" />
            </li>
          ))}
        </ol>
      </details>

      <div className="flex items-center gap-3">
        <Link
          href="/upload"
          className="inline-flex items-center gap-2 rounded-lg bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700"
        >
          Submit solution →
        </Link>
        <Link
          href="/survey"
          className="text-xs text-zinc-400 underline-offset-2 hover:text-zinc-600 hover:underline"
        >
          Retake survey
        </Link>
      </div>
    </div>
  );
}
