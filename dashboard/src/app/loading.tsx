export default function DashboardLoading() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="mb-8">
        <div className="h-8 w-40 animate-pulse rounded-lg bg-muted" />
        <div className="mt-2 h-4 w-72 animate-pulse rounded bg-muted" />
      </div>

      {/* Stats cards skeleton */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-border bg-card p-6 shadow-sm"
          >
            <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            <div className="mt-3 h-8 w-16 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>

      {/* Charts skeleton */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div
            key={i}
            className="rounded-xl border border-border bg-card p-6 shadow-sm"
          >
            <div className="h-4 w-32 animate-pulse rounded bg-muted" />
            <div className="mt-4 h-48 animate-pulse rounded bg-muted/50" />
          </div>
        ))}
      </div>
    </div>
  );
}
