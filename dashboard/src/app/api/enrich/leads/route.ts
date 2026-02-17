import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";

const SCRAPER_API_URL = process.env.SCRAPER_API_URL;
const SCRAPER_API_KEY = process.env.SCRAPER_API_KEY || "";

/**
 * POST /api/enrich/leads
 * Body: { leadIds: number[] }
 * Enriches specific leads by ID (single or bulk).
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const leadIds: number[] = body.leadIds;

    if (!leadIds || !Array.isArray(leadIds) || leadIds.length === 0) {
      return NextResponse.json(
        { error: "leadIds array is required" },
        { status: 400 }
      );
    }

    const validIds = leadIds.filter((id) => typeof id === "number" && id > 0);
    if (validIds.length === 0) {
      return NextResponse.json(
        { error: "No valid lead IDs provided" },
        { status: 400 }
      );
    }

    // Remote mode: proxy to FastAPI server
    if (SCRAPER_API_URL) {
      try {
        const res = await fetch(`${SCRAPER_API_URL}/enrich/leads`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": SCRAPER_API_KEY,
          },
          body: JSON.stringify({ lead_ids: validIds }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          return NextResponse.json(
            { error: errData.detail || "Enrichment failed on server" },
            { status: res.status }
          );
        }

        const data = await res.json();
        return NextResponse.json(data);
      } catch {
        return NextResponse.json(
          { error: "Failed to reach scraper server" },
          { status: 502 }
        );
      }
    }

    // Local mode: spawn Python CLI for each lead
    const projectRoot = path.resolve(process.cwd(), "..");

    const result = await new Promise<{ status: string; output: string[] }>(
      (resolve) => {
        const args = ["main.py", "enrich-leads", ...validIds.map(String)];
        const child = spawn("python3", args, {
          cwd: projectRoot,
          env: { ...process.env },
          stdio: ["ignore", "pipe", "pipe"],
        });

        const output: string[] = [];
        child.stdout?.on("data", (data: Buffer) => {
          output.push(...data.toString().split("\n").filter(Boolean));
        });
        child.stderr?.on("data", (data: Buffer) => {
          output.push(...data.toString().split("\n").filter(Boolean));
        });
        child.on("close", (code) => {
          resolve({
            status: code === 0 ? "completed" : "failed",
            output,
          });
        });
        child.on("error", (err) => {
          resolve({
            status: "failed",
            output: [`Process error: ${err.message}`],
          });
        });
      }
    );

    return NextResponse.json({
      status: result.status,
      enrichedIds: validIds,
      output: result.output,
    });
  } catch (error) {
    console.error("Enrich leads error:", error);
    return NextResponse.json(
      { error: "Failed to enrich leads" },
      { status: 500 }
    );
  }
}
