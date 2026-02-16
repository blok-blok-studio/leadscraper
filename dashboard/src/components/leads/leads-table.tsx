import Link from "next/link";
import { CheckCircle, XCircle } from "lucide-react";
import { formatPhone, qualityBadgeColor } from "@/lib/utils";

interface Lead {
  id: number;
  businessName: string;
  phone: string | null;
  email: string | null;
  city: string | null;
  state: string | null;
  category: string | null;
  qualityScore: number;
  isEnriched: boolean;
}

interface LeadsTableProps {
  leads: Lead[];
}

export function LeadsTable({ leads }: LeadsTableProps) {
  if (leads.length === 0) {
    return (
      <div className="bg-card rounded-xl border border-border p-12 text-center shadow-sm">
        <p className="text-muted-foreground">No leads found matching your filters.</p>
      </div>
    );
  }

  return (
    <div className="bg-card overflow-hidden rounded-xl border border-border shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Business Name
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Phone
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Email
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                City / State
              </th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                Category
              </th>
              <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                Quality
              </th>
              <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                Enriched
              </th>
            </tr>
          </thead>
          <tbody>
            {leads.map((lead, index) => (
              <tr
                key={lead.id}
                className={`border-b border-border transition-colors hover:bg-muted/30 ${
                  index % 2 === 0 ? "" : "bg-muted/20"
                }`}
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/leads/${lead.id}`}
                    className="font-medium text-primary hover:underline"
                  >
                    {lead.businessName}
                  </Link>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatPhone(lead.phone)}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {lead.email || "---"}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {[lead.city, lead.state].filter(Boolean).join(", ") || "---"}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {lead.category || "---"}
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${qualityBadgeColor(lead.qualityScore)}`}
                  >
                    {lead.qualityScore}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {lead.isEnriched ? (
                    <CheckCircle className="mx-auto h-4 w-4 text-emerald-500" />
                  ) : (
                    <XCircle className="mx-auto h-4 w-4 text-red-400" />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
