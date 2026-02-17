"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface ReEnrichStatus {
  status: "idle" | "running" | "completed" | "failed";
  output: string[];
  progress?: {
    staleFound: number;
    current: number;
    total: number;
    percent: number;
  };
}

export function ReEnrichButton({ enrichedCount }: { enrichedCount: number }) {
  const router = useRouter();
  const [state, setState] = useState<ReEnrichStatus>({ status: "idle", output: [] });
  const [showLog, setShowLog] = useState(false);
  const prevStatus = useRef(state.status);

  const poll = useCallback(async () => {
    try {
      const res = await fetch("/api/re-enrich");
      const data = await res.json();
      setState((prev) => ({
        ...prev,
        status: data.status,
        output: data.output || [],
        progress: data.progress,
      }));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    poll();
  }, [poll]);

  useEffect(() => {
    if (state.status === "running") {
      const interval = setInterval(poll, 2000);
      return () => clearInterval(interval);
    }
  }, [state.status, poll]);

  // Refresh page data when re-enrichment completes
  useEffect(() => {
    if (prevStatus.current === "running" && (state.status === "completed" || state.status === "failed")) {
      router.refresh();
    }
    prevStatus.current = state.status;
  }, [state.status, router]);

  const startReEnrich = async () => {
    setState({ status: "running", output: [] });
    setShowLog(true);
    try {
      const res = await fetch("/api/re-enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days: 30, limit: 50 }),
      });
      const data = await res.json();
      if (data.error) {
        setState((prev) => ({ ...prev, status: "running" }));
      }
    } catch {
      setState({ status: "failed", output: ["Failed to start re-enrichment"] });
    }
  };

  const percent = state.progress?.percent || 0;
  const staleFound = state.progress?.staleFound || 0;
  const current = state.progress?.current || 0;

  if (enrichedCount === 0 && state.status === "idle") {
    return null;
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-amber-50 p-2.5">
            <RefreshCw className="h-5 w-5 text-amber-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-card-foreground">
              Re-Enrichment
            </h3>
            <p className="text-xs text-muted-foreground">
              {state.status === "running"
                ? `Re-enriching ${current} of ${staleFound} stale leads...`
                : state.status === "completed"
                ? `Done — ${current} leads refreshed`
                : state.status === "failed"
                ? "Re-enrichment failed"
                : `Refresh data on leads older than 30 days`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {state.status === "running" ? (
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold tabular-nums text-amber-600">
                {percent}%
              </span>
              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center gap-2 rounded-lg bg-amber-100 px-4 py-2 text-sm font-medium text-amber-700"
              >
                <Loader2 className="h-4 w-4 animate-spin" />
                {showLog ? "Hide Log" : "Show Log"}
              </button>
            </div>
          ) : state.status === "completed" ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-600"
              >
                <CheckCircle2 className="h-4 w-4" />
                Done
              </button>
              <button
                onClick={startReEnrich}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700"
              >
                Run Again
              </button>
            </div>
          ) : state.status === "failed" ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-600"
              >
                <XCircle className="h-4 w-4" />
                Failed
              </button>
              <button
                onClick={startReEnrich}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700"
              >
                Retry
              </button>
            </div>
          ) : (
            <button
              onClick={startReEnrich}
              className="flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-700"
            >
              <RefreshCw className="h-4 w-4" />
              Re-Enrich Stale Leads
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {(state.status === "running" || state.status === "completed") && (
        <div className="mt-4 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {staleFound > 0 ? `${staleFound} stale leads found` : "Scanning for stale leads..."}
            </span>
            <span className="text-xs font-medium tabular-nums text-muted-foreground">
              {current}{staleFound > 0 ? ` / ${staleFound}` : ""}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-500 ease-out ${
                state.status === "completed" ? "bg-emerald-500" : "bg-amber-500"
              }`}
              style={{ width: `${Math.max(state.status === "completed" ? 100 : percent, 2)}%` }}
            />
          </div>
        </div>
      )}

      {/* Expandable log */}
      {showLog && state.output.length > 0 && (
        <div className="mt-3 max-h-48 overflow-y-auto rounded-lg bg-muted/30 p-3">
          {state.output.slice(-20).map((line, i) => (
            <p
              key={i}
              className={`font-mono text-xs ${
                line.includes("ERROR") || line.includes("Failed")
                  ? "text-red-500"
                  : line.includes("Enriched:")
                  ? "text-emerald-600"
                  : "text-muted-foreground"
              }`}
            >
              {line}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
