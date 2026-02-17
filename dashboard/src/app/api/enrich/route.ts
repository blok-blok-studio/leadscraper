import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const SCRAPER_API_URL = process.env.SCRAPER_API_URL;
const SCRAPER_API_KEY = process.env.SCRAPER_API_KEY || "";

// ---------------------------------------------------------------------------
// Remote mode: proxy to FastAPI server
// ---------------------------------------------------------------------------

async function remotePost(limit: number) {
  const res = await fetch(`${SCRAPER_API_URL}/enrich`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SCRAPER_API_KEY,
    },
    body: JSON.stringify({ limit }),
  });
  return res.json();
}

async function remoteGet() {
  const res = await fetch(`${SCRAPER_API_URL}/enrich`, {
    headers: { "X-API-Key": SCRAPER_API_KEY },
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Local mode: spawn Python CLI
// ---------------------------------------------------------------------------

let enrichJob: {
  status: "running" | "completed" | "failed";
  output: string[];
  startedAt: Date;
  limit: number;
} | null = null;

function parseProgress(output: string[]) {
  let current = 0;
  let total = 0;
  let lastBusiness = "";

  for (const line of output) {
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

    const totalMatch = line.match(/Total:\s+(\d+)\s+\|\s+Success:\s+(\d+)/);
    if (totalMatch) {
      total = parseInt(totalMatch[1], 10);
      current = parseInt(totalMatch[1], 10);
    }
  }

  if (total === 0 && current > 0) total = current;
  const percent = total > 0 ? Math.round((current / total) * 100) : 0;

  return { current, total, percent, lastBusiness };
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const limit = body.limit || 100;

  if (SCRAPER_API_URL) {
    try {
      const data = await remotePost(limit);
      return NextResponse.json(data);
    } catch {
      return NextResponse.json(
        { error: "Failed to reach scraper server" },
        { status: 502 }
      );
    }
  }

  // Local fallback
  if (enrichJob?.status === "running") {
    return NextResponse.json(
      { error: "Enrichment already running", status: "running" },
      { status: 409 }
    );
  }

  const projectRoot = path.resolve(process.cwd(), "..");

  const child = spawn(
    "python3",
    ["main.py", "enrich", "--limit", String(limit)],
    { cwd: projectRoot, env: { ...process.env }, stdio: ["ignore", "pipe", "pipe"] }
  );

  enrichJob = { status: "running", output: [], startedAt: new Date(), limit };

  child.stdout?.on("data", (data: Buffer) => {
    enrichJob?.output.push(...data.toString().split("\n").filter(Boolean));
  });
  child.stderr?.on("data", (data: Buffer) => {
    enrichJob?.output.push(...data.toString().split("\n").filter(Boolean));
  });
  child.on("close", (code) => {
    if (enrichJob) enrichJob.status = code === 0 ? "completed" : "failed";
  });
  child.on("error", (err) => {
    if (enrichJob) {
      enrichJob.status = "failed";
      enrichJob.output.push(`Process error: ${err.message}`);
    }
  });

  return NextResponse.json({ status: "running", limit });
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

  // Local fallback
  if (!enrichJob) {
    return NextResponse.json({ status: "idle" });
  }

  return NextResponse.json({
    status: enrichJob.status,
    output: enrichJob.output,
    startedAt: enrichJob.startedAt.toISOString(),
    limit: enrichJob.limit,
    progress: parseProgress(enrichJob.output),
  });
}
