"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { ScrapeForm } from "@/components/scrape/scrape-form";
import { JobTracker } from "@/components/scrape/job-tracker";

interface RunningJob {
  jobId: string;
  status: "running" | "completed" | "failed";
  output: string[];
  params: {
    source: string;
    category: string;
    location: string;
    pages: number;
  };
  startedAt: string;
  progress?: {
    current: number;
    total: number;
    percent: number;
    leadsFound?: number;
    leadsNew?: number;
    lastBusiness?: string;
  };
}

export default function ScrapePage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<RunningJob[]>([]);
  const hadRunning = useRef(false);

  const startScrape = async (params: {
    source: string;
    categories: string[];
    locations: string[];
    pages: number;
  }) => {
    // Launch one job per category+location combo
    for (const category of params.categories) {
      for (const location of params.locations) {
        try {
          const res = await fetch("/api/scrape", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source: params.source,
              category,
              location,
              pages: params.pages,
            }),
          });
          const data = await res.json();
          if (data.jobId) {
            setJobs((prev) => [
              {
                jobId: data.jobId,
                status: "running",
                output: [],
                params: { source: params.source, category, location, pages: params.pages },
                startedAt: new Date().toISOString(),
              },
              ...prev,
            ]);
          }
        } catch (err) {
          console.error("Failed to start scrape:", err);
        }
      }
    }
  };

  // Poll running jobs for status updates
  const pollJobs = useCallback(async () => {
    const running = jobs.filter((j) => j.status === "running");
    if (running.length === 0) return;

    for (const job of running) {
      try {
        const res = await fetch(`/api/scrape?jobId=${job.jobId}`);
        const data = await res.json();
        if (data.jobId) {
          setJobs((prev) =>
            prev.map((j) =>
              j.jobId === data.jobId
                ? { ...j, status: data.status, output: data.output, progress: data.progress }
                : j
            )
          );
        }
      } catch {
        // ignore poll errors
      }
    }
  }, [jobs]);

  useEffect(() => {
    if (jobs.some((j) => j.status === "running")) {
      const interval = setInterval(pollJobs, 2000);
      return () => clearInterval(interval);
    }
  }, [jobs, pollJobs]);

  // Refresh page data when all jobs finish so lead counts update
  useEffect(() => {
    const anyRunning = jobs.some((j) => j.status === "running");
    if (hadRunning.current && !anyRunning && jobs.length > 0) {
      router.refresh();
    }
    hadRunning.current = anyRunning;
  }, [jobs, router]);

  return (
    <>
      <Header
        title="Scrape Control"
        description="Configure and launch lead scraping jobs"
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Left: Configuration form */}
        <ScrapeForm onSubmit={startScrape} isRunning={jobs.some((j) => j.status === "running")} />

        {/* Right: Job tracker */}
        <JobTracker jobs={jobs} />
      </div>
    </>
  );
}
