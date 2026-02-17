"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface EnrichProgress {
  current: number;
  total: number;
  percent: number;
  lastBusiness: string;
}

interface EnrichStatus {
  status: "idle" | "running" | "completed" | "failed";
  output: string[];
  limit?: number;
  progress?: EnrichProgress;
}

export function EnrichButton({ unenrichedCount }: { unenrichedCount: number }) {
  const router = useRouter();
  const [state, setState] = useState<EnrichStatus>({ status: "idle", output: [] });
  const [showLog, setShowLog] = useState(false);
  const prevStatus = useRef(state.status);

  const poll = useCallback(async () => {
    try {
      const res = await fetch("/api/enrich");
      const data = await res.json();
      setState((prev) => ({
        ...prev,
        status: data.status,
        output: data.output || [],
        limit: data.limit,
        progress: data.progress,
      }));
    } catch {
      // ignore
    }
  }, []);

  // Check if enrichment is already running on mount
  useEffect(() => {
    poll();
  }, [poll]);

  // Poll while running
  useEffect(() => {
    if (state.status === "running") {
      const interval = setInterval(poll, 2000);
      return () => clearInterval(interval);
    }
  }, [state.status, poll]);

  // Refresh page data when enrichment completes so green checks update
  useEffect(() => {
    if (prevStatus.current === "running" && (state.status === "completed" || state.status === "failed")) {
      router.refresh();
    }
    prevStatus.current = state.status;
  }, [state.status, router]);

  const startEnrich = async () => {
    setState({ status: "running", output: [] });
    setShowLog(true);
    try {
      const res = await fetch("/api/enrich", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: unenrichedCount || 100 }),
      });
      const data = await res.json();
      if (data.error) {
        // Already running
        setState((prev) => ({ ...prev, status: "running" }));
      }
    } catch {
      setState({ status: "failed", output: ["Failed to start enrichment"] });
    }
  };

  // Count successes from output
  const successCount = state.progress?.current || state.output.filter((l) => l.includes("Enriched:")).length;
  const failCount = state.output.filter((l) => l.includes("Failed to enrich")).length;
  const percent = state.progress?.percent || 0;
  const total = state.progress?.total || 0;

  if (unenrichedCount === 0 && state.status === "idle") {
    return null;
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-violet-50 p-2.5">
            <Sparkles className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-card-foreground">
              Lead Enrichment
            </h3>
            <p className="text-xs text-muted-foreground">
              {state.status === "running"
                ? `Enriching ${successCount}${total > 0 ? ` of ${total}` : ""} leads...${failCount > 0 ? ` (${failCount} failed)` : ""}`
                : state.status === "completed"
                ? `Done — ${successCount} enriched${failCount > 0 ? `, ${failCount} failed` : ""}`
                : state.status === "failed"
                ? "Enrichment failed"
                : `${unenrichedCount} leads need enrichment (emails, tech stack, socials)`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {state.status === "running" ? (
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold tabular-nums text-violet-600">
                {percent}%
              </span>
              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center gap-2 rounded-lg bg-violet-100 px-4 py-2 text-sm font-medium text-violet-700"
              >
                <Loader2 className="h-4 w-4 animate-spin" />
                {showLog ? "Hide Log" : "Show Log"}
              </button>
            </div>
          ) : state.status === "completed" ? (
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tabular-nums text-emerald-600">
                100%
              </span>
              <button
                onClick={() => setShowLog(!showLog)}
                className="flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-600"
              >
                <CheckCircle2 className="h-4 w-4" />
                Done
              </button>
              {unenrichedCount > 0 && (
                <button
                  onClick={startEnrich}
                  className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700"
                >
                  Run Again
                </button>
              )}
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
                onClick={startEnrich}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700"
              >
                Retry
              </button>
            </div>
          ) : (
            <button
              onClick={startEnrich}
              className="flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700"
            >
              <Sparkles className="h-4 w-4" />
              Enrich {unenrichedCount} Leads
            </button>
          )}
        </div>
      </div>

      {/* Progress bar — always visible when running or just completed */}
      {(state.status === "running" || state.status === "completed") && (
        <div className="mt-4 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="truncate text-xs text-muted-foreground max-w-[70%]">
              {state.progress?.lastBusiness
                ? `Last: ${state.progress.lastBusiness}`
                : "Starting enrichment..."}
            </span>
            <span className="text-xs font-medium tabular-nums text-muted-foreground">
              {successCount}{total > 0 ? ` / ${total}` : ""}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-500 ease-out ${
                state.status === "completed"
                  ? "bg-emerald-500"
                  : "bg-violet-500"
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
