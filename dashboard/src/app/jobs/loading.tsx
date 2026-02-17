export default function JobsLoading() {
  return (
    <div className="space-y-4">
      {/* Header skeleton */}
      <div className="mb-8">
        <div className="h-8 w-32 animate-pulse rounded-lg bg-muted" />
        <div className="mt-2 h-4 w-40 animate-pulse rounded bg-muted" />
      </div>

      {/* Table skeleton */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <div className="border-b border-border bg-muted/50 px-4 py-3">
          <div className="flex gap-6">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-4 w-16 animate-pulse rounded bg-muted"
              />
            ))}
          </div>
        </div>

        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="flex gap-6 border-b border-border px-4 py-4"
          >
            <div className="h-4 w-8 animate-pulse rounded bg-muted" />
            <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            <div className="h-4 w-28 animate-pulse rounded bg-muted" />
            <div className="h-5 w-16 animate-pulse rounded-full bg-muted" />
            <div className="h-4 w-10 animate-pulse rounded bg-muted" />
            <div className="h-4 w-10 animate-pulse rounded bg-muted" />
            <div className="h-4 w-16 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}
