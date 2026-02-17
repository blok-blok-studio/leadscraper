import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const SCRAPER_API_URL = process.env.SCRAPER_API_URL;
const SCRAPER_API_KEY = process.env.SCRAPER_API_KEY || "";

// ---------------------------------------------------------------------------
// Remote mode
// ---------------------------------------------------------------------------

async function remotePost(days: number, limit: number) {
  const res = await fetch(`${SCRAPER_API_URL}/re-enrich`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SCRAPER_API_KEY,
    },
    body: JSON.stringify({ days, limit }),
  });
  return res.json();
}

async function remoteGet() {
  const res = await fetch(`${SCRAPER_API_URL}/re-enrich`, {
    headers: { "X-API-Key": SCRAPER_API_KEY },
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Local mode
// ---------------------------------------------------------------------------

let reEnrichJob: {
  status: "running" | "completed" | "failed";
  output: string[];
  startedAt: Date;
} | null = null;

function parseProgress(output: string[]) {
  let staleFound = 0;
  let current = 0;
  let total = 0;

  for (const line of output) {
    const staleMatch = line.match(/Found\s+(\d+)\s+stale/);
    if (staleMatch) staleFound = parseInt(staleMatch[1], 10);

    const resetMatch = line.match(/Reset\s+(\d+)\s+leads/);
    if (resetMatch) total = parseInt(resetMatch[1], 10);

    const enrichMatch = line.match(/Enriched:/);
    if (enrichMatch) current++;

    const totalMatch = line.match(/Total:\s+(\d+)\s+\|\s+Success:\s+(\d+)/);
    if (totalMatch) {
      total = parseInt(totalMatch[1], 10);
      current = parseInt(totalMatch[2], 10);
    }
  }

  if (total === 0 && staleFound > 0) total = staleFound;
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return { staleFound, current, total, percent };
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const days = body.days || 30;
  const limit = body.limit || 50;

  if (SCRAPER_API_URL) {
    try {
      const data = await remotePost(days, limit);
      return NextResponse.json(data);
    } catch {
      return NextResponse.json(
        { error: "Failed to reach scraper server" },
        { status: 502 }
      );
    }
  }

  // Local fallback
  if (reEnrichJob?.status === "running") {
    return NextResponse.json(
      { error: "Re-enrichment already running", status: "running" },
      { status: 409 }
    );
  }

  const projectRoot = path.resolve(process.cwd(), "..");

  const child = spawn(
    "python3",
    ["main.py", "re-enrich", "--days", String(days), "--limit", String(limit)],
    { cwd: projectRoot, env: { ...process.env }, stdio: ["ignore", "pipe", "pipe"] }
  );

  reEnrichJob = { status: "running", output: [], startedAt: new Date() };

  child.stdout?.on("data", (data: Buffer) => {
    reEnrichJob?.output.push(...data.toString().split("\n").filter(Boolean));
  });
  child.stderr?.on("data", (data: Buffer) => {
    reEnrichJob?.output.push(...data.toString().split("\n").filter(Boolean));
  });
  child.on("close", (code) => {
    if (reEnrichJob) reEnrichJob.status = code === 0 ? "completed" : "failed";
  });
  child.on("error", (err) => {
    if (reEnrichJob) {
      reEnrichJob.status = "failed";
      reEnrichJob.output.push(`Process error: ${err.message}`);
    }
  });

  return NextResponse.json({ status: "running", days, limit });
}

export async function GET() {
  if (SCRAPER_API_URL) {
    try {
      const data = await remoteGet();
      return NextResponse.json(data);
    } catch {
      return NextResponse.json({ status: "idle" });
    }
  }

  if (!reEnrichJob) {
    return NextResponse.json({ status: "idle" });
  }

  return NextResponse.json({
    status: reEnrichJob.status,
    output: reEnrichJob.output,
    startedAt: reEnrichJob.startedAt.toISOString(),
    progress: parseProgress(reEnrichJob.output),
  });
}
