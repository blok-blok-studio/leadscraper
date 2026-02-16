import { prisma } from "@/lib/prisma";
import { Header } from "@/components/layout/header";
import { JobStatusBadge } from "@/components/jobs/job-status-badge";
import { formatDate, formatDuration } from "@/lib/utils";

export default async function JobsPage() {
  const jobs = await prisma.scrapeJob.findMany({
    orderBy: { startedAt: "desc" },
  });

  return (
    <>
      <Header
        title="Scrape Jobs"
        description={`${jobs.length} jobs recorded`}
      />

      <div className="bg-card overflow-hidden rounded-xl border border-border shadow-sm">
        {jobs.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-muted-foreground">No scrape jobs recorded yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    Source
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    Category
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    Location
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    Found
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    New
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    Updated
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    Duration
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    Started
                  </th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job, index) => (
                  <tr
                    key={job.id}
                    className={`border-b border-border transition-colors hover:bg-muted/30 ${
                      index % 2 === 0 ? "" : "bg-muted/20"
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                      #{job.id}
                    </td>
                    <td className="px-4 py-3 font-medium text-card-foreground">
                      {job.source || "---"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {job.category || "---"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {job.location || "---"}
                    </td>
                    <td className="px-4 py-3">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-4 py-3 text-right text-card-foreground">
                      {job.leadsFound}
                    </td>
                    <td className="px-4 py-3 text-right text-emerald-600">
                      {job.leadsNew}
                    </td>
                    <td className="px-4 py-3 text-right text-blue-600">
                      {job.leadsUpdated}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {formatDuration(job.durationSeconds)}
                    </td>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {formatDate(job.startedAt)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
