import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const SCRAPER_API_URL = process.env.SCRAPER_API_URL; // e.g. http://your-server:8000
const SCRAPER_API_KEY = process.env.SCRAPER_API_KEY || "";

// ---------------------------------------------------------------------------
// Remote mode: proxy to FastAPI server
// ---------------------------------------------------------------------------

async function remotePost(body: Record<string, unknown>) {
  const res = await fetch(`${SCRAPER_API_URL}/scrape`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SCRAPER_API_KEY,
    },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function remoteGet(jobId?: string) {
  const url = jobId
    ? `${SCRAPER_API_URL}/scrape/${jobId}`
    : `${SCRAPER_API_URL}/scrape`;
  const res = await fetch(url, {
    headers: { "X-API-Key": SCRAPER_API_KEY },
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Local mode: spawn Python CLI (same machine)
// ---------------------------------------------------------------------------

const runningJobs = new Map<
  string,
  {
    process: ReturnType<typeof spawn>;
    status: "running" | "completed" | "failed";
    output: string[];
    startedAt: Date;
    params: { source: string; category: string; location: string; pages: number };
  }
>();

function cleanOldJobs() {
  const cutoff = Date.now() - 10 * 60 * 1000;
  for (const [id, job] of runningJobs) {
    if (job.status !== "running" && job.startedAt.getTime() < cutoff) {
      runningJobs.delete(id);
    }
  }
}

function parseProgress(output: string[]) {
  let current = 0;
  let total = 0;
  let leadsFound = 0;
  let leadsNew = 0;
  let lastBusiness = "";

  for (const line of output) {
    const foundMatch = line.match(/(\d+)\s+found,\s+(\d+)\s+new/);
    if (foundMatch) {
      leadsFound += parseInt(foundMatch[1], 10);
      leadsNew += parseInt(foundMatch[2], 10);
    }

    const enrichMatch = line.match(/Enriched:\s+(.+?)\s+\|/);
    if (enrichMatch) {
      current++;
      lastBusiness = enrichMatch[1];
    }

    const progressMatch = line.match(/Enrichment progress:\s+(\d+)\/(\d+)/);
    if (progressMatch) {
      current = parseInt(progressMatch[1], 10);
      total = parseInt(progressMatch[2], 10);
    }

    const autoEnrichMatch = line.match(/Auto-enriching\s+(\d+)/);
    if (autoEnrichMatch) {
      total = parseInt(autoEnrichMatch[1], 10);
      current = 0;
    }

    const totalMatch = line.match(/Total:\s+(\d+)\s+\|\s+Success:\s+(\d+)/);
    if (totalMatch) {
      total = parseInt(totalMatch[1], 10);
      current = parseInt(totalMatch[1], 10);
    }

    const scrapeMatch = line.match(/Found:\s+(\d+)\s+\|\s+New:\s+(\d+)/);
    if (scrapeMatch) {
      leadsFound = parseInt(scrapeMatch[1], 10);
      leadsNew = parseInt(scrapeMatch[2], 10);
    }
  }

  if (total === 0 && current > 0) total = current;
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return { current, total, percent, leadsFound, leadsNew, lastBusiness };
}

function localPost(body: {
  source: string;
  category: string;
  location: string;
  pages: number;
}) {
  cleanOldJobs();
  const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const projectRoot = path.resolve(process.cwd(), "..");

  const child = spawn(
    "python3",
    [
      "main.py",
      "scrape",
      "--source",
      body.source,
      "--category",
      body.category,
      "--location",
      body.location,
      "--pages",
      String(body.pages),
    ],
    { cwd: projectRoot, env: { ...process.env }, stdio: ["ignore", "pipe", "pipe"] }
  );

  const job = {
    process: child,
    status: "running" as const,
    output: [] as string[],
    startedAt: new Date(),
    params: body,
  };
  runningJobs.set(jobId, job);

  child.stdout?.on("data", (data: Buffer) => {
    job.output.push(...data.toString().split("\n").filter(Boolean));
  });
  child.stderr?.on("data", (data: Buffer) => {
    job.output.push(...data.toString().split("\n").filter(Boolean));
  });
  child.on("close", (code) => {
    const entry = runningJobs.get(jobId);
    if (entry) entry.status = code === 0 ? "completed" : "failed";
  });
  child.on("error", (err) => {
    const entry = runningJobs.get(jobId);
    if (entry) {
      entry.status = "failed";
      entry.output.push(`Process error: ${err.message}`);
    }
  });

  return { jobId, status: "running" };
}

function localGet(jobId?: string) {
  if (jobId) {
    const job = runningJobs.get(jobId);
    if (!job) return null;
    return {
      jobId,
      status: job.status,
      output: job.output,
      params: job.params,
      startedAt: job.startedAt.toISOString(),
      progress: parseProgress(job.output),
    };
  }

  return {
    jobs: Array.from(runningJobs.entries()).map(([id, job]) => ({
      jobId: id,
      status: job.status,
      params: job.params,
      startedAt: job.startedAt.toISOString(),
      outputLines: job.output.length,
    })),
  };
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { source = "googlemaps", category, location, pages = 5 } = body;

  if (!category || !location) {
    return NextResponse.json(
      { error: "category and location are required" },
      { status: 400 }
    );
  }

  if (SCRAPER_API_URL) {
    const data = await remotePost({ source, category, location, pages });
    return NextResponse.json(data);
  }

  const result = localPost({ source, category, location, pages });
  return NextResponse.json(result);
}

export async function GET(request: NextRequest) {
  const jobId = request.nextUrl.searchParams.get("jobId");

  if (SCRAPER_API_URL) {
    const data = await remoteGet(jobId || undefined);
    return NextResponse.json(data);
  }

  const result = localGet(jobId || undefined);
  if (jobId && !result) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }
  return NextResponse.json(result);
}
