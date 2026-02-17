export default function LeadDetailLoading() {
  return (
    <div className="space-y-6">
      {/* Back button + header skeleton */}
      <div className="mb-8">
        <div className="mb-3 h-4 w-20 animate-pulse rounded bg-muted" />
        <div className="h-8 w-64 animate-pulse rounded-lg bg-muted" />
        <div className="mt-2 h-4 w-48 animate-pulse rounded bg-muted" />
      </div>

      {/* Detail sections skeleton */}
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-border bg-card p-6 shadow-sm"
        >
          <div className="mb-4 h-5 w-28 animate-pulse rounded bg-muted" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, j) => (
              <div key={j}>
                <div className="h-3 w-20 animate-pulse rounded bg-muted" />
                <div className="mt-2 h-4 w-32 animate-pulse rounded bg-muted" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
