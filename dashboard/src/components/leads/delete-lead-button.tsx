"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Loader2 } from "lucide-react";

interface DeleteLeadButtonProps {
  leadId: number;
  businessName: string;
  /** Where to redirect after deletion. Defaults to /leads */
  redirectTo?: string;
  /** Compact mode for table rows */
  compact?: boolean;
}

export function DeleteLeadButton({
  leadId,
  businessName,
  redirectTo = "/leads",
  compact = false,
}: DeleteLeadButtonProps) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      // Navigate immediately — don't wait for the API
      router.push(redirectTo);

      const res = await fetch("/api/leads", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: [leadId] }),
      });

      if (res.ok) {
        router.refresh();
      }
    } catch {
      // Already navigated, not much to do
    }
  };

  if (confirming) {
    return (
      <div className={`flex items-center gap-2 ${compact ? "" : "rounded-lg border border-red-200 bg-red-50 px-3 py-2"}`}>
        <span className={`text-red-600 ${compact ? "text-xs" : "text-sm"}`}>
          {compact ? "Delete?" : `Delete "${businessName}"?`}
        </span>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="inline-flex items-center gap-1 rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
        >
          {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
          Yes
        </button>
        <button
          onClick={() => setConfirming(false)}
          className="rounded-md bg-white px-2.5 py-1 text-xs font-medium text-gray-600 ring-1 ring-gray-200 transition-colors hover:bg-gray-50"
        >
          No
        </button>
      </div>
    );
  }

  if (compact) {
    return (
      <button
        onClick={() => setConfirming(true)}
        className="rounded p-1 text-muted-foreground transition-colors hover:bg-red-50 hover:text-red-600"
        title="Delete lead"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
    >
      <Trash2 className="h-4 w-4" />
      Delete
    </button>
  );
}
