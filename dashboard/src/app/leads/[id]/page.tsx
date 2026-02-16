import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import { Header } from "@/components/layout/header";
import { LeadDetailSections } from "@/components/leads/lead-detail-sections";
import { qualityBadgeColor } from "@/lib/utils";
import Link from "next/link";
import { ArrowLeft, CheckCircle, XCircle } from "lucide-react";

interface LeadDetailPageProps {
  params: Promise<{ id: string }>;
}

export default async function LeadDetailPage({ params }: LeadDetailPageProps) {
  const { id } = await params;
  const leadId = parseInt(id, 10);

  if (isNaN(leadId)) {
    notFound();
  }

  const lead = await prisma.lead.findUnique({
    where: { id: leadId },
  });

  if (!lead) {
    notFound();
  }

  return (
    <>
      <div className="mb-6">
        <Link
          href="/leads"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Leads
        </Link>
      </div>

      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {lead.businessName}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {[lead.city, lead.state, lead.zipCode].filter(Boolean).join(", ")}
            {lead.category ? ` — ${lead.category}` : ""}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${qualityBadgeColor(lead.qualityScore)}`}
          >
            Quality: {lead.qualityScore}/100
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${
              lead.isEnriched
                ? "bg-emerald-100 text-emerald-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {lead.isEnriched ? (
              <CheckCircle className="h-3.5 w-3.5" />
            ) : (
              <XCircle className="h-3.5 w-3.5" />
            )}
            {lead.isEnriched ? "Enriched" : "Not Enriched"}
          </span>
        </div>
      </div>

      <LeadDetailSections lead={lead as unknown as Record<string, unknown>} />
    </>
  );
}
