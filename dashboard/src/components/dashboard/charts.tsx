"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

interface ChartsProps {
  byState: { state: string; _count: number }[];
  byCategory: { category: string; _count: number }[];
}

const BAR_COLOR = "#2563eb";

export function Charts({ byState, byCategory }: ChartsProps) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Leads by State - Horizontal Bar Chart */}
      <div className="bg-card rounded-xl border border-border p-6 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-card-foreground">
          Leads by State (Top 10)
        </h3>
        {byState.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No data available
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={byState}
              layout="vertical"
              margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis type="number" fontSize={12} tick={{ fill: "#64748b" }} />
              <YAxis
                dataKey="state"
                type="category"
                fontSize={12}
                tick={{ fill: "#64748b" }}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  fontSize: "13px",
                }}
              />
              <Bar dataKey="_count" name="Leads" radius={[0, 4, 4, 0]}>
                {byState.map((_, index) => (
                  <Cell key={`state-${index}`} fill={BAR_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Leads by Category - Vertical Bar Chart */}
      <div className="bg-card rounded-xl border border-border p-6 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-card-foreground">
          Leads by Category (Top 10)
        </h3>
        {byCategory.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No data available
          </p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={byCategory}
              margin={{ top: 0, right: 20, left: 0, bottom: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                dataKey="category"
                fontSize={11}
                tick={{ fill: "#64748b" }}
                angle={-35}
                textAnchor="end"
                height={60}
                interval={0}
              />
              <YAxis fontSize={12} tick={{ fill: "#64748b" }} />
              <Tooltip
                contentStyle={{
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  fontSize: "13px",
                }}
              />
              <Bar dataKey="_count" name="Leads" radius={[4, 4, 0, 0]}>
                {byCategory.map((_, index) => (
                  <Cell key={`cat-${index}`} fill={BAR_COLOR} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
