import { prisma } from "@/lib/prisma";
import { Prisma } from "@prisma/client";
import { Header } from "@/components/layout/header";
import { LeadFilters } from "@/components/leads/lead-filters";
import { LeadsTable } from "@/components/leads/leads-table";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

const PAGE_SIZE = 25;

interface LeadsPageProps {
  searchParams: Promise<{
    search?: string;
    state?: string;
    category?: string;
    minQuality?: string;
    enriched?: string;
    page?: string;
  }>;
}

export default async function LeadsPage({ searchParams }: LeadsPageProps) {
  const params = await searchParams;
  const currentPage = Math.max(1, parseInt(params.page ?? "1", 10));

  // Build where clause
  const where: Prisma.LeadWhereInput = {};

  if (params.search) {
    const term = params.search;
    where.OR = [
      { businessName: { contains: term, mode: "insensitive" } },
      { email: { contains: term, mode: "insensitive" } },
      { phone: { contains: term } },
    ];
  }

  if (params.state) {
    where.state = params.state;
  }

  if (params.category) {
    where.category = params.category;
  }

  if (params.minQuality) {
    where.qualityScore = { gte: parseInt(params.minQuality, 10) };
  }

  if (params.enriched === "true") {
    where.isEnriched = true;
  }

  // Parallel queries
  const [leads, totalCount, statesRaw, categoriesRaw] = await Promise.all([
    prisma.lead.findMany({
      where,
      select: {
        id: true,
        businessName: true,
        phone: true,
        email: true,
        city: true,
        state: true,
        category: true,
        qualityScore: true,
        isEnriched: true,
      },
      orderBy: { id: "desc" },
      skip: (currentPage - 1) * PAGE_SIZE,
      take: PAGE_SIZE,
    }),
    prisma.lead.count({ where }),
    prisma.lead.findMany({
      where: { state: { not: null } },
      select: { state: true },
      distinct: ["state"],
      orderBy: { state: "asc" },
    }),
    prisma.lead.findMany({
      where: { category: { not: null } },
      select: { category: true },
      distinct: ["category"],
      orderBy: { category: "asc" },
    }),
  ]);

  const states = statesRaw
    .map((r) => r.state)
    .filter((s): s is string => s !== null);
  const categories = categoriesRaw
    .map((r) => r.category)
    .filter((c): c is string => c !== null);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  // Build pagination URL helper
  function pageUrl(page: number): string {
    const p = new URLSearchParams();
    if (params.search) p.set("search", params.search);
    if (params.state) p.set("state", params.state);
    if (params.category) p.set("category", params.category);
    if (params.minQuality) p.set("minQuality", params.minQuality);
    if (params.enriched) p.set("enriched", params.enriched);
    if (page > 1) p.set("page", String(page));
    const qs = p.toString();
    return `/leads${qs ? `?${qs}` : ""}`;
  }

  return (
    <>
      <Header
        title="Leads"
        description={`${totalCount.toLocaleString()} leads in database`}
      />

      <div className="space-y-4">
        <LeadFilters states={states} categories={categories} />

        <LeadsTable leads={leads} />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {(currentPage - 1) * PAGE_SIZE + 1}--
              {Math.min(currentPage * PAGE_SIZE, totalCount)} of{" "}
              {totalCount.toLocaleString()}
            </p>

            <div className="flex items-center gap-2">
              {currentPage > 1 ? (
                <Link
                  href={pageUrl(currentPage - 1)}
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-card-foreground transition-colors hover:bg-muted"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Link>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-lg border border-border bg-muted px-3 py-2 text-sm font-medium text-muted-foreground">
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </span>
              )}

              <span className="px-3 text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>

              {currentPage < totalPages ? (
                <Link
                  href={pageUrl(currentPage + 1)}
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-card-foreground transition-colors hover:bg-muted"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Link>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-lg border border-border bg-muted px-3 py-2 text-sm font-medium text-muted-foreground">
                  Next
                  <ChevronRight className="h-4 w-4" />
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
