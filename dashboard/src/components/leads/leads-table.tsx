"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle, XCircle, Trash2, Loader2, Sparkles } from "lucide-react";
import { formatPhone, qualityBadgeColor, icpBadgeColor, icpLabel } from "@/lib/utils";

interface Lead {
  id: number;
  businessName: string;
  phone: string | null;
  email: string | null;
  city: string | null;
  state: string | null;
  category: string | null;
  qualityScore: number;
  icpScore: number;
  isEnriched: boolean;
}

interface LeadsTableProps {
  leads: Lead[];
}

export function LeadsTable({ leads }: LeadsTableProps) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deletedIds, setDeletedIds] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [enrichingIds, setEnrichingIds] = useState<Set<number>>(new Set());
  const [enrichingBulk, setEnrichingBulk] = useState(false);
  const [isPending, startTransition] = useTransition();

  // Filter out optimistically deleted leads
  const visibleLeads = leads.filter((l) => !deletedIds.has(l.id));

  const allSelected = visibleLeads.length > 0 && selected.size === visibleLeads.length;
  const someSelected = selected.size > 0;

  // Count unenriched among selected
  const selectedUnenriched = visibleLeads.filter(
    (l) => selected.has(l.id) && !l.isEnriched
  );

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(visibleLeads.map((l) => l.id)));
    }
  };

  const toggleOne = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleEnrichSingle = async (leadId: number) => {
    setEnrichingIds((prev) => new Set([...prev, leadId]));

    try {
      const res = await fetch("/api/enrich/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadIds: [leadId] }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.error || "Failed to enrich lead");
      } else {
        startTransition(() => {
          router.refresh();
        });
      }
    } catch {
      alert("Failed to enrich lead");
    } finally {
      setEnrichingIds((prev) => {
        const next = new Set(prev);
        next.delete(leadId);
        return next;
      });
    }
  };

  const handleEnrichSelected = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;

    setEnrichingBulk(true);
    setEnrichingIds((prev) => new Set([...prev, ...ids]));

    try {
      const res = await fetch("/api/enrich/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadIds: ids }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.error || "Failed to enrich leads");
      } else {
        startTransition(() => {
          router.refresh();
        });
      }
    } catch {
      alert("Failed to enrich leads");
    } finally {
      setEnrichingBulk(false);
      setEnrichingIds(new Set());
    }
  };

  const handleEnrichAll = async () => {
    const unenrichedIds = visibleLeads
      .filter((l) => !l.isEnriched)
      .map((l) => l.id);

    if (unenrichedIds.length === 0) {
      alert("All visible leads are already enriched");
      return;
    }

    setEnrichingBulk(true);
    setEnrichingIds(new Set(unenrichedIds));

    try {
      const res = await fetch("/api/enrich/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leadIds: unenrichedIds }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        alert(data.error || "Failed to enrich leads");
      } else {
        startTransition(() => {
          router.refresh();
        });
      }
    } catch {
      alert("Failed to enrich leads");
    } finally {
      setEnrichingBulk(false);
      setEnrichingIds(new Set());
    }
  };

  const handleBulkDelete = async () => {
    if (selected.size === 0) return;
    setDeleting(true);

    const idsToDelete = Array.from(selected);

    // Optimistically remove from UI immediately
    setDeletedIds((prev) => new Set([...prev, ...idsToDelete]));
    setSelected(new Set());
    setConfirming(false);

    try {
      const res = await fetch("/api/leads", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: idsToDelete }),
      });

      if (!res.ok) {
        // Revert on failure
        setDeletedIds((prev) => {
          const next = new Set(prev);
          idsToDelete.forEach((id) => next.delete(id));
          return next;
        });
        alert("Failed to delete leads");
      } else {
        // Refresh server data in background (non-blocking)
        startTransition(() => {
          router.refresh();
        });
      }
    } catch {
      // Revert on error
      setDeletedIds((prev) => {
        const next = new Set(prev);
        idsToDelete.forEach((id) => next.delete(id));
        return next;
      });
      alert("Failed to delete leads");
    } finally {
      setDeleting(false);
    }
  };

  if (visibleLeads.length === 0) {
    return (
      <div className="bg-card rounded-xl border border-border p-12 text-center shadow-sm">
        <p className="text-muted-foreground">No leads found matching your filters.</p>
      </div>
    );
  }

  const unenrichedCount = visibleLeads.filter((l) => !l.isEnriched).length;

  return (
    <div className="space-y-2">
      {/* Top action bar: Enrich All button always visible */}
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-2.5 shadow-sm">
        <span className="text-sm text-muted-foreground">
          {visibleLeads.length} leads{" "}
          {unenrichedCount > 0 && (
            <span className="text-amber-600">({unenrichedCount} unenriched)</span>
          )}
        </span>

        <button
          onClick={handleEnrichAll}
          disabled={enrichingBulk || unenrichedCount === 0}
          className="inline-flex items-center gap-1.5 rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
        >
          {enrichingBulk ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          Enrich All ({unenrichedCount})
        </button>
      </div>

      {/* Bulk action bar (when items selected) */}
      {someSelected && (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5 shadow-sm">
          <span className="text-sm font-medium text-card-foreground">
            {selected.size} selected
          </span>

          {/* Enrich selected */}
          <button
            onClick={handleEnrichSelected}
            disabled={enrichingBulk}
            className="inline-flex items-center gap-1.5 rounded-md border border-violet-200 bg-white px-3 py-1.5 text-xs font-medium text-violet-600 transition-colors hover:bg-violet-50 disabled:opacity-50"
          >
            {enrichingBulk ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Sparkles className="h-3.5 w-3.5" />
            )}
            Enrich selected
          </button>

          {/* Delete selected */}
          {confirming ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-red-600">
                Delete {selected.size} lead{selected.size > 1 ? "s" : ""}?
              </span>
              <button
                onClick={handleBulkDelete}
                disabled={deleting}
                className="inline-flex items-center gap-1 rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                Yes, delete
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="rounded-md bg-white px-3 py-1.5 text-xs font-medium text-gray-600 ring-1 ring-gray-200 transition-colors hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete selected
            </button>
          )}

          <button
            onClick={() => {
              setSelected(new Set());
              setConfirming(false);
            }}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            Clear selection
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-card overflow-hidden rounded-xl border border-border shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="w-10 px-3 py-3 text-center">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected && !allSelected;
                    }}
                    onChange={toggleAll}
                    className="h-4 w-4 rounded border-gray-300 accent-violet-600"
                  />
                </th>
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
                  ICP
                </th>
                <th className="px-4 py-3 text-center font-medium text-muted-foreground">
                  Enriched
                </th>
                <th className="w-20 px-4 py-3 text-center font-medium text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleLeads.map((lead, index) => {
                const isEnriching = enrichingIds.has(lead.id);
                return (
                  <tr
                    key={lead.id}
                    className={`border-b border-border transition-colors hover:bg-muted/30 ${
                      index % 2 === 0 ? "" : "bg-muted/20"
                    } ${selected.has(lead.id) ? "bg-violet-50/50" : ""}`}
                  >
                    <td className="w-10 px-3 py-3 text-center">
                      <input
                        type="checkbox"
                        checked={selected.has(lead.id)}
                        onChange={() => toggleOne(lead.id)}
                        className="h-4 w-4 rounded border-gray-300 accent-violet-600"
                      />
                    </td>
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
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${icpBadgeColor(lead.icpScore)}`}
                        title={`ICP Score: ${lead.icpScore}/100 — ${icpLabel(lead.icpScore)}`}
                      >
                        {lead.icpScore}
                        <span className="hidden sm:inline text-[10px] opacity-75">{icpLabel(lead.icpScore)}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {lead.isEnriched ? (
                        <CheckCircle className="mx-auto h-4 w-4 text-emerald-500" />
                      ) : (
                        <XCircle className="mx-auto h-4 w-4 text-red-400" />
                      )}
                    </td>
                    <td className="w-20 px-4 py-3 text-center">
                      <button
                        onClick={() => handleEnrichSingle(lead.id)}
                        disabled={isEnriching}
                        title={lead.isEnriched ? "Re-enrich this lead" : "Enrich this lead"}
                        className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-white px-2 py-1 text-[11px] font-medium text-violet-600 transition-colors hover:bg-violet-50 disabled:opacity-50"
                      >
                        {isEnriching ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Sparkles className="h-3 w-3" />
                        )}
                        {isEnriching ? "" : "Enrich"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
