import { prisma } from "@/lib/prisma";
import { Header } from "@/components/layout/header";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { Charts } from "@/components/dashboard/charts";
import { RecentJobs } from "@/components/dashboard/recent-jobs";

export default async function DashboardPage() {
  const [
    totalLeads,
    enrichedLeads,
    avgQualityResult,
    distinctSources,
    byStateRaw,
    byCategoryRaw,
    recentJobs,
  ] = await Promise.all([
    prisma.lead.count(),
    prisma.lead.count({ where: { isEnriched: true } }),
    prisma.lead.aggregate({ _avg: { qualityScore: true } }),
    prisma.lead.findMany({
      select: { source: true },
      distinct: ["source"],
    }),
    prisma.lead.groupBy({
      by: ["state"],
      _count: { _all: true },
      where: { state: { not: null } },
      orderBy: { _count: { state: "desc" } },
      take: 10,
    }),
    prisma.lead.groupBy({
      by: ["category"],
      _count: { _all: true },
      where: { category: { not: null } },
      orderBy: { _count: { category: "desc" } },
      take: 10,
    }),
    prisma.scrapeJob.findMany({
      orderBy: { startedAt: "desc" },
      take: 5,
    }),
  ]);

  const avgQuality = Math.round(avgQualityResult._avg.qualityScore ?? 0);
  const sourcesActive = distinctSources.length;

  const byState = byStateRaw.map((row) => ({
    state: row.state ?? "Unknown",
    _count: row._count._all,
  }));

  const byCategory = byCategoryRaw.map((row) => ({
    category: row.category ?? "Unknown",
    _count: row._count._all,
  }));

  return (
    <>
      <Header
        title="Dashboard"
        description="Overview of your lead scraping pipeline"
      />

      <div className="space-y-6">
        <StatsCards
          totalLeads={totalLeads}
          enrichedLeads={enrichedLeads}
          avgQuality={avgQuality}
          sourcesActive={sourcesActive}
        />

        <Charts byState={byState} byCategory={byCategory} />

        <RecentJobs jobs={recentJobs} />
      </div>
    </>
  );
}
