import { Database, CheckCircle, TrendingUp, Target, Globe } from "lucide-react";

interface StatsCardsProps {
  totalLeads: number;
  enrichedLeads: number;
  avgQuality: number;
  avgIcp: number;
  sourcesActive: number;
}

const cards = [
  {
    key: "total",
    label: "Total Leads",
    icon: Database,
    color: "text-blue-600 bg-blue-50",
  },
  {
    key: "enriched",
    label: "Enriched",
    icon: CheckCircle,
    color: "text-emerald-600 bg-emerald-50",
  },
  {
    key: "quality",
    label: "Avg Quality",
    icon: TrendingUp,
    color: "text-amber-600 bg-amber-50",
  },
  {
    key: "icp",
    label: "Avg ICP Score",
    icon: Target,
    color: "text-violet-600 bg-violet-50",
  },
  {
    key: "sources",
    label: "Sources Active",
    icon: Globe,
    color: "text-purple-600 bg-purple-50",
  },
] as const;

export function StatsCards({
  totalLeads,
  enrichedLeads,
  avgQuality,
  avgIcp,
  sourcesActive,
}: StatsCardsProps) {
  const icpLabel = avgIcp >= 70 ? "Hot" : avgIcp >= 40 ? "Warm" : avgIcp >= 20 ? "Cool" : "Cold";

  const values: Record<string, { value: string; subtitle: string }> = {
    total: {
      value: totalLeads.toLocaleString(),
      subtitle: "in database",
    },
    enriched: {
      value: enrichedLeads.toLocaleString(),
      subtitle: `${totalLeads > 0 ? Math.round((enrichedLeads / totalLeads) * 100) : 0}% of total`,
    },
    quality: {
      value: `${avgQuality}`,
      subtitle: "out of 100",
    },
    icp: {
      value: `${avgIcp}`,
      subtitle: `${icpLabel} — out of 100`,
    },
    sources: {
      value: `${sourcesActive}`,
      subtitle: "unique sources",
    },
  };

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-5">
      {cards.map((card) => {
        const Icon = card.icon;
        const data = values[card.key];
        return (
          <div
            key={card.key}
            className="bg-card rounded-xl border border-border p-6 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  {card.label}
                </p>
                <p className="mt-2 text-3xl font-bold text-card-foreground">
                  {data.value}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {data.subtitle}
                </p>
              </div>
              <div className={`rounded-lg p-3 ${card.color}`}>
                <Icon className="h-6 w-6" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
