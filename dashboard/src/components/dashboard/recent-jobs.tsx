import { formatDate, formatDuration } from "@/lib/utils";
import { JobStatusBadge } from "@/components/jobs/job-status-badge";

interface Job {
  id: number;
  source: string | null;
  category: string | null;
  location: string | null;
  status: string;
  leadsFound: number;
  durationSeconds: number | null;
  startedAt: Date;
}

interface RecentJobsProps {
  jobs: Job[];
}

export function RecentJobs({ jobs }: RecentJobsProps) {
  return (
    <div className="bg-card rounded-xl border border-border p-6 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-card-foreground">
        Recent Scrape Jobs
      </h3>
      {jobs.length === 0 ? (
        <p className="py-4 text-center text-sm text-muted-foreground">
          No jobs yet
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="pb-3 pr-4 font-medium text-muted-foreground">
                  Source
                </th>
                <th className="pb-3 pr-4 font-medium text-muted-foreground">
                  Category
                </th>
                <th className="pb-3 pr-4 font-medium text-muted-foreground">
                  Location
                </th>
                <th className="pb-3 pr-4 font-medium text-muted-foreground">
                  Status
                </th>
                <th className="pb-3 pr-4 text-right font-medium text-muted-foreground">
                  Found
                </th>
                <th className="pb-3 pr-4 text-right font-medium text-muted-foreground">
                  Duration
                </th>
                <th className="pb-3 text-right font-medium text-muted-foreground">
                  Time
                </th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-border last:border-0"
                >
                  <td className="py-3 pr-4 font-medium text-card-foreground">
                    {job.source || "—"}
                  </td>
                  <td className="py-3 pr-4 text-muted-foreground">
                    {job.category || "—"}
                  </td>
                  <td className="py-3 pr-4 text-muted-foreground">
                    {job.location || "—"}
                  </td>
                  <td className="py-3 pr-4">
                    <JobStatusBadge status={job.status} />
                  </td>
                  <td className="py-3 pr-4 text-right text-card-foreground">
                    {job.leadsFound}
                  </td>
                  <td className="py-3 pr-4 text-right text-muted-foreground">
                    {formatDuration(job.durationSeconds)}
                  </td>
                  <td className="py-3 text-right text-muted-foreground">
                    {formatDate(job.startedAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
