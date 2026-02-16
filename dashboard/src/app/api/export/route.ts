import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { Prisma } from "@prisma/client";

const CSV_COLUMNS = [
  { key: "id", label: "ID" },
  { key: "businessName", label: "Business Name" },
  { key: "phone", label: "Phone" },
  { key: "email", label: "Email" },
  { key: "website", label: "Website" },
  { key: "address", label: "Address" },
  { key: "city", label: "City" },
  { key: "state", label: "State" },
  { key: "zipCode", label: "ZIP Code" },
  { key: "category", label: "Category" },
  { key: "subcategory", label: "Subcategory" },
  { key: "ownerName", label: "Owner Name" },
  { key: "ownerTitle", label: "Owner Title" },
  { key: "ownerEmail", label: "Owner Email" },
  { key: "ownerPhone", label: "Owner Phone" },
  { key: "ownerLinkedin", label: "Owner LinkedIn" },
  { key: "employeeCount", label: "Employees" },
  { key: "annualRevenueEstimate", label: "Revenue Estimate" },
  { key: "yearEstablished", label: "Year Established" },
  { key: "businessType", label: "Business Type" },
  { key: "facebookUrl", label: "Facebook" },
  { key: "instagramUrl", label: "Instagram" },
  { key: "twitterUrl", label: "Twitter" },
  { key: "linkedinUrl", label: "LinkedIn" },
  { key: "googleRating", label: "Google Rating" },
  { key: "googleReviewCount", label: "Google Reviews" },
  { key: "yelpRating", label: "Yelp Rating" },
  { key: "yelpReviewCount", label: "Yelp Reviews" },
  { key: "qualityScore", label: "Quality Score" },
  { key: "isEnriched", label: "Enriched" },
  { key: "source", label: "Source" },
  { key: "scrapedAt", label: "Scraped At" },
] as const;

function escapeCsv(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const format = searchParams.get("format") || "csv";
  const state = searchParams.get("state");
  const category = searchParams.get("category");
  const minQuality = searchParams.get("minQuality");
  const enrichedOnly = searchParams.get("enrichedOnly");

  // Build where clause
  const where: Prisma.LeadWhereInput = {};

  if (state) {
    where.state = state;
  }

  if (category) {
    where.category = category;
  }

  if (minQuality) {
    where.qualityScore = { gte: parseInt(minQuality, 10) };
  }

  if (enrichedOnly === "true") {
    where.isEnriched = true;
  }

  const leads = await prisma.lead.findMany({
    where,
    orderBy: { id: "desc" },
  });

  const timestamp = new Date().toISOString().slice(0, 10);

  if (format === "json") {
    return new NextResponse(JSON.stringify(leads, null, 2), {
      headers: {
        "Content-Type": "application/json",
        "Content-Disposition": `attachment; filename="leads-${timestamp}.json"`,
      },
    });
  }

  // CSV format
  const header = CSV_COLUMNS.map((c) => c.label).join(",");
  const rows = leads.map((lead) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const record = lead as Record<string, any>;
    return CSV_COLUMNS.map((col) => escapeCsv(record[col.key])).join(",");
  });
  const csv = [header, ...rows].join("\n");

  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="leads-${timestamp}.csv"`,
    },
  });
}
