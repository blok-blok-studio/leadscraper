"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCallback } from "react";
import { Search, Filter } from "lucide-react";

interface LeadFiltersProps {
  states: string[];
  categories: string[];
}

export function LeadFilters({ states, categories }: LeadFiltersProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentSearch = searchParams.get("search") ?? "";
  const currentState = searchParams.get("state") ?? "";
  const currentCategory = searchParams.get("category") ?? "";
  const currentEnriched = searchParams.get("enriched") ?? "";
  const currentMinQuality = searchParams.get("minQuality") ?? "";

  const updateParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      // Reset to page 1 on filter change
      params.delete("page");
      router.push(`${pathname}?${params.toString()}`);
    },
    [router, pathname, searchParams],
  );

  return (
    <div className="bg-card rounded-xl border border-border p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative min-w-[240px] flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search business name, email, phone..."
            defaultValue={currentSearch}
            onChange={(e) => {
              // Debounce-like: update on blur or enter
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                updateParam("search", e.currentTarget.value);
              }
            }}
            onBlur={(e) => updateParam("search", e.currentTarget.value)}
            className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* State filter */}
        <select
          value={currentState}
          onChange={(e) => updateParam("state", e.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All States</option>
          {states.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        {/* Category filter */}
        <select
          value={currentCategory}
          onChange={(e) => updateParam("category", e.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        {/* Min Quality */}
        <select
          value={currentMinQuality}
          onChange={(e) => updateParam("minQuality", e.target.value)}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        >
          <option value="">Any Quality</option>
          <option value="70">70+</option>
          <option value="50">50+</option>
          <option value="30">30+</option>
        </select>

        {/* Enriched toggle */}
        <button
          onClick={() =>
            updateParam("enriched", currentEnriched === "true" ? "" : "true")
          }
          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
            currentEnriched === "true"
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-background text-muted-foreground hover:border-primary hover:text-foreground"
          }`}
        >
          <Filter className="h-3.5 w-3.5" />
          Enriched Only
        </button>
      </div>
    </div>
  );
}
