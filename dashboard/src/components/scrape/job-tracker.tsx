"use client";

import { CheckCircle2, XCircle, Loader2, Terminal } from "lucide-react";

interface Progress {
  current: number;
  total: number;
  percent: number;
  leadsFound?: number;
  leadsNew?: number;
  lastBusiness?: string;
}

interface RunningJob {
  jobId: string;
  status: "running" | "completed" | "failed";
  output: string[];
  params: {
    source: string;
    category: string;
    location: string;
    pages: number;
  };
  startedAt: string;
  progress?: Progress;
}

interface JobTrackerProps {
  jobs: RunningJob[];
}

export function JobTracker({ jobs }: JobTrackerProps) {
  if (jobs.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
        <div className="flex flex-col items-center justify-center text-center">
          <Terminal className="mb-3 h-10 w-10 text-muted-foreground/30" />
          <h3 className="text-sm font-semibold text-card-foreground">
            No jobs running
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Configure your scrape parameters and click Launch to start.
          </p>
        </div>
      </div>
    );
  }

  const running = jobs.filter((j) => j.status === "running").length;
  const completed = jobs.filter((j) => j.status === "completed").length;
  const failed = jobs.filter((j) => j.status === "failed").length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex gap-3">
        {running > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-600">
            <Loader2 className="h-3 w-3 animate-spin" />
            {running} running
          </div>
        )}
        {completed > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-600">
            <CheckCircle2 className="h-3 w-3" />
            {completed} completed
          </div>
        )}
        {failed > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-600">
            <XCircle className="h-3 w-3" />
            {failed} failed
          </div>
        )}
      </div>

      {/* Job cards */}
      <div className="space-y-3">
        {jobs.map((job) => (
          <div
            key={job.jobId}
            className="rounded-xl border border-border bg-card shadow-sm"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-3">
                {job.status === "running" ? (
                  <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                ) : job.status === "completed" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                <div>
                  <p className="text-sm font-medium text-card-foreground">
                    {job.params.category} in {job.params.location}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {job.params.source} &middot; {job.params.pages} pages
                  </p>
                </div>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  job.status === "running"
                    ? "bg-blue-500/10 text-blue-600"
                    : job.status === "completed"
                    ? "bg-emerald-500/10 text-emerald-600"
                    : "bg-red-500/10 text-red-600"
                }`}
              >
                {job.status}
              </span>
            </div>

            {/* Progress bar */}
            {job.status === "running" && (
              <div className="px-4 py-3">
                <ProgressBar progress={job.progress} output={job.output} />
              </div>
            )}

            {/* Completed summary */}
            {job.status === "completed" && job.progress && (
              <div className="px-4 py-3">
                <ProgressBar progress={{ ...job.progress, percent: 100 }} output={job.output} />
              </div>
            )}

            {/* Output log (last 6 lines) */}
            {job.output.length > 0 && (
              <div className="max-h-28 overflow-y-auto border-t border-border bg-muted/30 px-4 py-2">
                {job.output.slice(-6).map((line, i) => (
                  <p
                    key={i}
                    className={`font-mono text-xs ${
                      line.includes("ERROR") || line.includes("Failed")
                        ? "text-red-500"
                        : line.includes("Enriched:")
                        ? "text-emerald-600"
                        : line.includes("found") || line.includes("New:")
                        ? "text-blue-600"
                        : "text-muted-foreground"
                    }`}
                  >
                    {line}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Reusable progress bar with percentage */
function ProgressBar({
  progress,
  output,
}: {
  progress?: Progress;
  output: string[];
}) {
  const enrichedCount =
    progress?.current ||
    output.filter((l) => l.includes("Enriched:")).length;
  const total = progress?.total || 0;
  const percent = progress?.percent || 0;
  const lastBusiness = progress?.lastBusiness || "";
  const leadsFound = progress?.leadsFound || 0;
  const leadsNew = progress?.leadsNew || 0;

  // Build status text
  let statusText = "";
  if (leadsFound > 0) {
    statusText = `${leadsFound} found · ${leadsNew} new`;
  }
  if (enrichedCount > 0 && total > 0) {
    statusText = `Enriching ${enrichedCount} of ${total}`;
  } else if (enrichedCount > 0) {
    statusText = `${enrichedCount} enriched`;
  }
  if (lastBusiness && enrichedCount > 0) {
    statusText += ` · ${lastBusiness}`;
  }
  if (!statusText) {
    statusText = "Starting...";
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="truncate text-xs text-muted-foreground max-w-[70%]">
          {statusText}
        </span>
        <span className="text-sm font-bold tabular-nums text-card-foreground">
          {percent}%
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${
            percent >= 100
              ? "bg-emerald-500"
              : "bg-blue-500"
          }`}
          style={{ width: `${Math.max(percent, 2)}%` }}
        />
      </div>
    </div>
  );
}
