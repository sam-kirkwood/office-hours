"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import SkillTreeView from "./SkillTreeView";
import type { NodeVariant } from "./SkillTree";
import { computePlanMembership, effectiveTopicState } from "@/lib/plan";
import type {
  CanonicalTopic,
  CanonicalEdge,
  SurveyPayload,
  Subtopic,
  TopicEntry,
  TopicState,
  TopicStateMap,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Static configuration
// ---------------------------------------------------------------------------

const DEGREE_OPTIONS = ["None", "Bachelor's", "Master's", "PhD"];

const YEARS_OPTIONS = [
  { value: "current", label: "Currently studying" },
  { value: "<1", label: "Less than 1 year ago" },
  { value: "1-3", label: "1–3 years ago" },
  { value: "3-10", label: "3–10 years ago" },
  { value: "10+", label: "More than 10 years ago" },
];

const DIFFICULTY_OPTIONS = [
  {
    value: "gentle",
    label: "Gentle",
    description: "Start easy, build confidence gradually",
  },
  {
    value: "standard",
    label: "Standard",
    description: "Balanced pace, appropriate challenge",
  },
  {
    value: "aggressive",
    label: "Aggressive",
    description: "Jump in at the deep end",
  },
] as const;

const SECTION_LABELS = ["Background", "Plan", "Preferences"];

const STATE_CYCLE: (TopicState | null)[] = [
  "target",
  "known",
  "refresher",
  null,
];

interface FormState {
  degrees: string[];
  yearsSinceStudy: string;
  degreeFields: string;
  currentField: string;
  topicStates: TopicStateMap;
  extraTopics: string;
  difficultyCurve: string;
}

const INITIAL_STATE: FormState = {
  degrees: [],
  yearsSinceStudy: "",
  degreeFields: "",
  currentField: "",
  topicStates: {},
  extraTopics: "",
  difficultyCurve: "",
};

// ---------------------------------------------------------------------------
// State helpers
// ---------------------------------------------------------------------------

function entryIsEmpty(entry: TopicEntry | undefined): boolean {
  if (!entry) return true;
  if (entry.state) return false;
  if (entry.subtopics && Object.keys(entry.subtopics).length > 0) return false;
  return true;
}

function setTopicLevelState(
  map: TopicStateMap,
  topicId: string,
  state: TopicState | null
): TopicStateMap {
  const next = { ...map };
  const current = next[topicId] ?? {};
  const updated: TopicEntry = { ...current };
  if (state === null) delete updated.state;
  else updated.state = state;
  if (entryIsEmpty(updated)) delete next[topicId];
  else next[topicId] = updated;
  return next;
}

function setSubtopicLevelState(
  map: TopicStateMap,
  topicId: string,
  subtopicSlug: string,
  state: TopicState | null
): TopicStateMap {
  const next = { ...map };
  const current = next[topicId] ?? {};
  const subs = { ...(current.subtopics ?? {}) };
  if (state === null) delete subs[subtopicSlug];
  else subs[subtopicSlug] = state;
  const updated: TopicEntry = {
    ...current,
    subtopics: Object.keys(subs).length > 0 ? subs : undefined,
  };
  if (entryIsEmpty(updated)) delete next[topicId];
  else next[topicId] = updated;
  return next;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  topics: CanonicalTopic[];
  edges: CanonicalEdge[];
}

export default function SurveyForm({ topics, edges }: Props) {
  const router = useRouter();
  const [section, setSection] = useState(0);
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const topicsByDomain = useMemo(
    () =>
      topics.reduce<Record<string, CanonicalTopic[]>>((acc, t) => {
        (acc[t.domain] ??= []).push(t);
        return acc;
      }, {}),
    [topics]
  );

  function canAdvance(): boolean {
    if (section === 0) {
      return form.degrees.length > 0 && form.yearsSinceStudy !== "";
    }
    if (section === 1) {
      return topics.some(
        (t) => effectiveTopicState(form.topicStates[t.id], t) === "target"
      );
    }
    if (section === 2) {
      return form.difficultyCurve !== "";
    }
    return true;
  }

  function toggleDegree(deg: string) {
    setForm((f) => ({
      ...f,
      degrees: f.degrees.includes(deg)
        ? f.degrees.filter((d) => d !== deg)
        : [...f.degrees, deg],
    }));
  }

  function setTopicState(id: string, state: TopicState | null) {
    setForm((f) => ({ ...f, topicStates: setTopicLevelState(f.topicStates, id, state) }));
  }

  function cycleTopicState(id: string) {
    const current = form.topicStates[id]?.state ?? null;
    const next = STATE_CYCLE[(STATE_CYCLE.indexOf(current) + 1) % STATE_CYCLE.length];
    setTopicState(id, next);
  }

  function setSubtopicState(
    topicId: string,
    slug: string,
    state: TopicState | null
  ) {
    setForm((f) => ({
      ...f,
      topicStates: setSubtopicLevelState(f.topicStates, topicId, slug, state),
    }));
  }

  async function handleSubmit() {
    setError(null);
    setSubmitting(true);

    const payload: SurveyPayload = {
      background: {
        degrees: form.degrees,
        yearsSinceStudy: form.yearsSinceStudy,
        degreeFields: form.degreeFields,
        currentField: form.currentField,
      },
      topicStates: form.topicStates,
      extraTopics: form.extraTopics,
      difficultyCurve: form.difficultyCurve as SurveyPayload["difficultyCurve"],
    };

    try {
      const res = await fetch("/api/survey", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error ?? "Something went wrong");
      }
      router.push("/plan");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
      setSubmitting(false);
    }
  }

  const containerWidth = section === 1 ? "max-w-6xl" : "max-w-2xl";

  return (
    <div className={`mx-auto ${containerWidth} px-4 py-10`}>
      <div className="mb-8">
        <div className="mb-2 flex items-center justify-between text-sm text-zinc-500">
          <span>
            Step {section + 1} of {SECTION_LABELS.length}
          </span>
          <span>{SECTION_LABELS[section]}</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-zinc-100">
          <div
            className="h-1.5 rounded-full bg-zinc-900 transition-all"
            style={{
              width: `${((section + 1) / SECTION_LABELS.length) * 100}%`,
            }}
          />
        </div>
      </div>

      {section === 0 && (
        <BackgroundSection
          form={form}
          setForm={setForm}
          toggleDegree={toggleDegree}
        />
      )}

      {section === 1 && (
        <PlanBuilderSection
          topics={topics}
          edges={edges}
          topicsByDomain={topicsByDomain}
          topicStates={form.topicStates}
          setTopicState={setTopicState}
          setSubtopicState={setSubtopicState}
          cycleTopicState={cycleTopicState}
          extraTopics={form.extraTopics}
          setExtraTopics={(v) => setForm((f) => ({ ...f, extraTopics: v }))}
        />
      )}

      {section === 2 && (
        <PreferencesSection
          difficultyCurve={form.difficultyCurve}
          setDifficultyCurve={(v) =>
            setForm((f) => ({ ...f, difficultyCurve: v }))
          }
        />
      )}

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <div className="mt-8 flex gap-3">
        {section > 0 && (
          <button
            type="button"
            onClick={() => setSection((s) => s - 1)}
            disabled={submitting}
            className="rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:opacity-50"
          >
            Back
          </button>
        )}
        <div className="flex-1" />
        {section < SECTION_LABELS.length - 1 ? (
          <button
            type="button"
            onClick={() => setSection((s) => s + 1)}
            disabled={!canAdvance()}
            className="rounded-lg bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-40"
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canAdvance() || submitting}
            className="rounded-lg bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:opacity-40"
          >
            {submitting ? "Building your plan…" : "Generate my plan →"}
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section components
// ---------------------------------------------------------------------------

function BackgroundSection({
  form,
  setForm,
  toggleDegree,
}: {
  form: FormState;
  setForm: React.Dispatch<React.SetStateAction<FormState>>;
  toggleDegree: (deg: string) => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-zinc-900">
        Tell us about your background
      </h1>

      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-700">
          Degrees held{" "}
          <span className="text-zinc-400">(tick all that apply)</span>
        </label>
        <div className="flex flex-wrap gap-2">
          {DEGREE_OPTIONS.map((deg) => (
            <button
              key={deg}
              type="button"
              onClick={() => toggleDegree(deg)}
              className={`rounded-lg border px-4 py-2 text-sm transition ${
                form.degrees.includes(deg)
                  ? "border-zinc-900 bg-zinc-900 text-white"
                  : "border-zinc-300 text-zinc-700 hover:border-zinc-500"
              }`}
            >
              {deg}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label
          htmlFor="years"
          className="mb-1 block text-sm font-medium text-zinc-700"
        >
          Years since last formal study
        </label>
        <select
          id="years"
          value={form.yearsSinceStudy}
          onChange={(e) =>
            setForm((f) => ({ ...f, yearsSinceStudy: e.target.value }))
          }
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200"
        >
          <option value="">Select…</option>
          {YEARS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="degreeFields"
          className="mb-1 block text-sm font-medium text-zinc-700"
        >
          What did you study?{" "}
          <span className="font-normal text-zinc-400">(optional)</span>
        </label>
        <input
          id="degreeFields"
          type="text"
          value={form.degreeFields}
          onChange={(e) =>
            setForm((f) => ({ ...f, degreeFields: e.target.value }))
          }
          placeholder="e.g. Physics, Computer Science"
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200"
        />
      </div>

      <div>
        <label
          htmlFor="currentField"
          className="mb-1 block text-sm font-medium text-zinc-700"
        >
          What do you do now?{" "}
          <span className="font-normal text-zinc-400">(optional)</span>
        </label>
        <input
          id="currentField"
          type="text"
          value={form.currentField}
          onChange={(e) =>
            setForm((f) => ({ ...f, currentField: e.target.value }))
          }
          placeholder="e.g. Software engineering, Medicine"
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200"
        />
      </div>
    </div>
  );
}

function PlanBuilderSection({
  topics,
  edges,
  topicsByDomain,
  topicStates,
  setTopicState,
  setSubtopicState,
  cycleTopicState,
  extraTopics,
  setExtraTopics,
}: {
  topics: CanonicalTopic[];
  edges: CanonicalEdge[];
  topicsByDomain: Record<string, CanonicalTopic[]>;
  topicStates: TopicStateMap;
  setTopicState: (id: string, state: TopicState | null) => void;
  setSubtopicState: (
    topicId: string,
    slug: string,
    state: TopicState | null
  ) => void;
  cycleTopicState: (id: string) => void;
  extraTopics: string;
  setExtraTopics: (v: string) => void;
}) {
  const planMembership = useMemo(
    () => computePlanMembership(topicStates, topics, edges),
    [topicStates, topics, edges]
  );

  const variants = useMemo<Record<string, NodeVariant>>(() => {
    const v: Record<string, NodeVariant> = {};
    for (const topic of topics) {
      const eff = effectiveTopicState(topicStates[topic.id], topic);
      if (eff === "target") v[topic.id] = "target";
      else if (eff === "known") v[topic.id] = "known";
      else if (eff === "refresher") v[topic.id] = "refresher";
      else if (planMembership.has(topic.id)) v[topic.id] = "needed";
      else v[topic.id] = "context";
    }
    return v;
  }, [topics, topicStates, planMembership]);

  const counts = useMemo(() => {
    const c = { target: 0, known: 0, refresher: 0, plan: planMembership.size };
    for (const topic of topics) {
      const eff = effectiveTopicState(topicStates[topic.id], topic);
      if (eff === "target") c.target += 1;
      else if (eff === "known") c.known += 1;
      else if (eff === "refresher") c.refresher += 1;
    }
    return c;
  }, [topics, topicStates, planMembership]);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-zinc-900">
          Build your plan
        </h1>
        <p className="text-sm text-zinc-500">
          Mark each topic: <strong>★</strong> to learn it, <strong>✓</strong> to
          skip (you already know it), <strong>↻</strong> for a lighter
          refresher. Blank topics aren&apos;t in your plan unless they&apos;re a
          prerequisite of a target.
        </p>
        <p className="mt-1.5 text-sm text-zinc-500">
          Expand any row to fine-tune at the subtopic level — customizing any
          subtopic automatically pulls the topic into your plan.
        </p>
      </div>

      <Counter counts={counts} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[360px_1fr]">
        <TopicList
          topicsByDomain={topicsByDomain}
          topicStates={topicStates}
          setTopicState={setTopicState}
          setSubtopicState={setSubtopicState}
          inPlan={planMembership}
        />

        <div className="flex flex-col gap-2">
          <SkillTreeView
            topics={topics}
            edges={edges}
            variants={variants}
            onNodeClick={cycleTopicState}
            height={600}
          />
          <p className="text-center text-xs text-zinc-400">
            Click any topic in the graph to cycle: ★ target → ✓ known → ↻
            refresher → clear
          </p>
        </div>
      </div>

      <div>
        <label
          htmlFor="extra"
          className="mb-1 block text-sm font-medium text-zinc-700"
        >
          Anything missing?{" "}
          <span className="font-normal text-zinc-400">(optional)</span>
        </label>
        <textarea
          id="extra"
          rows={2}
          value={extraTopics}
          onChange={(e) => setExtraTopics(e.target.value)}
          placeholder="e.g. General relativity, fluid mechanics, numerical methods…"
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none transition focus:border-zinc-500 focus:ring-2 focus:ring-zinc-200"
        />
        <p className="mt-1 text-xs text-zinc-400">
          We&apos;ll note these for review and add them to the curriculum.
        </p>
      </div>
    </div>
  );
}

function Counter({
  counts,
}: {
  counts: { target: number; known: number; refresher: number; plan: number };
}) {
  if (counts.target === 0) {
    return (
      <div className="rounded-lg border border-dashed border-blue-300 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        Pick at least one ★ <strong>target topic</strong> to get started — your
        plan will fill in its prerequisites automatically.
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1.5 rounded-lg bg-zinc-50 px-4 py-3 text-sm ring-1 ring-zinc-200">
      <span>
        <strong className="text-zinc-900">{counts.plan}</strong>{" "}
        <span className="text-zinc-500">topics in plan</span>
      </span>
      <span className="text-zinc-300">·</span>
      <span>
        <strong className="text-blue-700">{counts.target}</strong>{" "}
        <span className="text-zinc-500">target{counts.target === 1 ? "" : "s"}</span>
      </span>
      <span>
        <strong className="text-emerald-700">{counts.known}</strong>{" "}
        <span className="text-zinc-500">already known</span>
      </span>
      <span>
        <strong className="text-amber-700">{counts.refresher}</strong>{" "}
        <span className="text-zinc-500">refresher{counts.refresher === 1 ? "" : "s"}</span>
      </span>
    </div>
  );
}

function TopicList({
  topicsByDomain,
  topicStates,
  setTopicState,
  setSubtopicState,
  inPlan,
}: {
  topicsByDomain: Record<string, CanonicalTopic[]>;
  topicStates: TopicStateMap;
  setTopicState: (id: string, state: TopicState | null) => void;
  setSubtopicState: (
    topicId: string,
    slug: string,
    state: TopicState | null
  ) => void;
  inPlan: Set<string>;
}) {
  return (
    <div
      className="flex flex-col gap-3 overflow-y-auto rounded-lg border border-zinc-200 bg-white p-3"
      style={{ maxHeight: 640 }}
    >
      {Object.entries(topicsByDomain).map(([domain, domainTopics]) => (
        <div key={domain}>
          <h2 className="mb-1.5 px-1 text-xs font-semibold uppercase tracking-wider text-zinc-400">
            {domain}
          </h2>
          <div className="flex flex-col gap-1">
            {domainTopics
              .slice()
              .sort((a, b) => {
                const order = { intro: 0, core: 1, advanced: 2 };
                return order[a.difficulty_band] - order[b.difficulty_band];
              })
              .map((topic) => (
                <TopicRow
                  key={topic.id}
                  topic={topic}
                  entry={topicStates[topic.id]}
                  isPrereq={!topicStates[topic.id] && inPlan.has(topic.id)}
                  setState={(s) => setTopicState(topic.id, s)}
                  setSubtopicState={(slug, s) =>
                    setSubtopicState(topic.id, slug, s)
                  }
                />
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function TopicRow({
  topic,
  entry,
  isPrereq,
  setState,
  setSubtopicState,
}: {
  topic: CanonicalTopic;
  entry: TopicEntry | undefined;
  isPrereq: boolean;
  setState: (state: TopicState | null) => void;
  setSubtopicState: (slug: string, state: TopicState | null) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const state = entry?.state;
  const subtopicCount = entry?.subtopics
    ? Object.keys(entry.subtopics).length
    : 0;
  const subtopics: Subtopic[] = topic.subtopics ?? [];
  const canExpand = subtopics.length > 0;
  const rowBg = isPrereq ? "bg-blue-50/60" : "";

  return (
    <div className={`rounded-md ${rowBg}`}>
      <div className="flex items-center gap-2 px-2 py-1.5">
        <button
          type="button"
          onClick={() => canExpand && setExpanded((e) => !e)}
          disabled={!canExpand}
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-xs text-zinc-400 transition hover:text-zinc-700 disabled:opacity-30"
          aria-label={expanded ? "Collapse" : "Expand"}
        >
          <span
            className="inline-block transition-transform"
            style={{
              transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            }}
          >
            ▶
          </span>
        </button>

        <button
          type="button"
          onClick={() => canExpand && setExpanded((e) => !e)}
          className="min-w-0 flex-1 text-left"
        >
          <p className="truncate text-sm font-medium text-zinc-900">
            {topic.title}
            {subtopicCount > 0 && (
              <span
                className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-zinc-400 align-middle"
                title={`${subtopicCount} subtopic${subtopicCount === 1 ? "" : "s"} customised`}
              />
            )}
            {isPrereq && (
              <span className="ml-1.5 text-[10px] font-normal uppercase tracking-wide text-blue-600">
                included
              </span>
            )}
          </p>
        </button>

        <div className="flex shrink-0 gap-1">
          <StateButton
            active={state === "target"}
            onClick={() => setState(state === "target" ? null : "target")}
            title="I want to learn this"
            activeClass="bg-blue-600 text-white border-blue-700"
          >
            ★
          </StateButton>
          <StateButton
            active={state === "known"}
            onClick={() => setState(state === "known" ? null : "known")}
            title="I already know this"
            activeClass="bg-emerald-600 text-white border-emerald-700"
          >
            ✓
          </StateButton>
          <StateButton
            active={state === "refresher"}
            onClick={() => setState(state === "refresher" ? null : "refresher")}
            title="I'd like a refresher"
            activeClass="bg-amber-500 text-white border-amber-600"
          >
            ↻
          </StateButton>
        </div>
      </div>

      {expanded && canExpand && (
        <div className="ml-7 mr-2 mb-1 flex flex-col gap-0.5 border-l border-zinc-100 pl-2">
          {subtopics.map((sub) => {
            const subState = entry?.subtopics?.[sub.slug];
            return (
              <div
                key={sub.slug}
                className="flex items-center gap-2 px-1 py-1"
              >
                <p className="min-w-0 flex-1 truncate text-xs text-zinc-600">
                  {sub.title}
                </p>
                <div className="flex shrink-0 gap-1">
                  <StateButton
                    active={subState === "target"}
                    onClick={() =>
                      setSubtopicState(
                        sub.slug,
                        subState === "target" ? null : "target"
                      )
                    }
                    title="Focus on this subtopic"
                    activeClass="bg-blue-600 text-white border-blue-700"
                    size="sm"
                  >
                    ★
                  </StateButton>
                  <StateButton
                    active={subState === "known"}
                    onClick={() =>
                      setSubtopicState(
                        sub.slug,
                        subState === "known" ? null : "known"
                      )
                    }
                    title="I know this part"
                    activeClass="bg-emerald-600 text-white border-emerald-700"
                    size="sm"
                  >
                    ✓
                  </StateButton>
                  <StateButton
                    active={subState === "refresher"}
                    onClick={() =>
                      setSubtopicState(
                        sub.slug,
                        subState === "refresher" ? null : "refresher"
                      )
                    }
                    title="Light pass on this part"
                    activeClass="bg-amber-500 text-white border-amber-600"
                    size="sm"
                  >
                    ↻
                  </StateButton>
                </div>
              </div>
            );
          })}
          <p className="px-1 pt-1 pb-0.5 text-[10px] text-zinc-400">
            Blank subtopics get the standard treatment. Custom subtopic
            preferences will fine-tune problem selection.
          </p>
        </div>
      )}
    </div>
  );
}

function StateButton({
  active,
  onClick,
  title,
  activeClass,
  size = "md",
  children,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  activeClass: string;
  size?: "sm" | "md";
  children: React.ReactNode;
}) {
  const dim = size === "sm" ? "h-5 w-5 text-[10px]" : "h-6 w-6 text-xs";
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`flex items-center justify-center rounded border transition ${dim} ${
        active
          ? activeClass
          : "border-zinc-200 text-zinc-400 hover:border-zinc-400 hover:text-zinc-700"
      }`}
    >
      {children}
    </button>
  );
}

function PreferencesSection({
  difficultyCurve,
  setDifficultyCurve,
}: {
  difficultyCurve: string;
  setDifficultyCurve: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="mb-1 text-xl font-semibold text-zinc-900">
          How would you like to learn?
        </h1>
        <p className="text-sm text-zinc-500">
          This sets the difficulty of the first few problems.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {DIFFICULTY_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setDifficultyCurve(opt.value)}
            className={`flex items-start gap-3 rounded-xl border px-5 py-4 text-left transition ${
              difficultyCurve === opt.value
                ? "border-zinc-900 bg-zinc-900 text-white"
                : "border-zinc-200 hover:border-zinc-400"
            }`}
          >
            <div>
              <p className="font-medium">{opt.label}</p>
              <p
                className={`text-sm ${
                  difficultyCurve === opt.value
                    ? "text-zinc-300"
                    : "text-zinc-500"
                }`}
              >
                {opt.description}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
