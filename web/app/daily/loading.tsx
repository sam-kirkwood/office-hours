// Shown during the ~10–30s cold Sonnet wait on first visit of the day when
// the (topic, difficulty, hook) cache misses. Cache hits are sub-second and
// rarely show this skeleton at all.

export default function Loading() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-10 animate-pulse">
      <div className="mb-8 rounded-xl bg-zinc-100 px-5 py-4 ring-1 ring-zinc-200">
        <div className="mb-3 h-4 w-32 rounded bg-zinc-200" />
        <div className="space-y-2">
          <div className="h-3 w-full rounded bg-zinc-200" />
          <div className="h-3 w-11/12 rounded bg-zinc-200" />
          <div className="h-3 w-9/12 rounded bg-zinc-200" />
        </div>
      </div>

      <div className="mb-4 h-5 w-44 rounded bg-zinc-200" />
      <div className="mb-6 rounded-xl bg-white px-5 py-4 ring-1 ring-zinc-200">
        <div className="space-y-2">
          <div className="h-3 w-full rounded bg-zinc-100" />
          <div className="h-3 w-10/12 rounded bg-zinc-100" />
          <div className="h-3 w-8/12 rounded bg-zinc-100" />
        </div>
      </div>

      <div className="mb-8 rounded-xl bg-zinc-50 px-5 py-3 ring-1 ring-zinc-200">
        <div className="h-3 w-24 rounded bg-zinc-200" />
      </div>

      <p className="text-xs text-zinc-400">
        Picking your problem… first visit each day takes a few seconds.
      </p>
    </div>
  );
}
