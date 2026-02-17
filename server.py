"""
FastAPI server — remote API wrapper for the scraper engine.

Run on your scraping server so the Vercel dashboard can trigger
scrapes, enrichment, and re-enrichment over HTTP.

Usage:
    SCRAPER_API_KEY=your-secret python3 server.py
    # or
    SCRAPER_API_KEY=your-secret uvicorn server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.engine import ScraperEngine

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("SCRAPER_API_KEY", "")

app = FastAPI(title="LeadScraper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def verify_api_key(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# In-memory job tracking
# ---------------------------------------------------------------------------

jobs: dict[str, dict] = {}

# Enrichment is a singleton — only one at a time
enrich_state: dict = {"status": "idle", "output": [], "progress": {}}


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:8]}"


def _clean_old_jobs():
    cutoff = datetime.now(timezone.utc).timestamp() - 600  # 10 min
    to_delete = [
        jid for jid, j in jobs.items()
        if j["status"] != "running" and j.get("started_ts", 0) < cutoff
    ]
    for jid in to_delete:
        del jobs[jid]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ScrapeRequest(BaseModel):
    source: str = "googlemaps"
    category: str
    location: str
    pages: int = 5


class EnrichRequest(BaseModel):
    limit: int = 100


class EnrichLeadsRequest(BaseModel):
    lead_ids: list[int]


class ReEnrichRequest(BaseModel):
    days: int = 30
    limit: int = 50


# ---------------------------------------------------------------------------
# Scrape endpoints
# ---------------------------------------------------------------------------

@app.post("/scrape", dependencies=[Depends(verify_api_key)])
async def start_scrape(req: ScrapeRequest):
    _clean_old_jobs()
    job_id = _new_job_id()

    jobs[job_id] = {
        "status": "running",
        "output": [],
        "params": req.model_dump(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_ts": datetime.now(timezone.utc).timestamp(),
        "progress": {},
    }

    async def _run():
        try:
            engine = ScraperEngine()
            jobs[job_id]["output"].append(
                f"Scraping {req.source} for '{req.category}' in {req.location}..."
            )
            result = await engine.scrape_single_source(
                source=req.source,
                category=req.category,
                location=req.location,
                max_pages=req.pages,
            )
            jobs[job_id]["output"].append(
                f"Found: {result.get('found', 0)} | "
                f"New: {result.get('new', 0)} | "
                f"Updated: {result.get('updated', 0)}"
            )
            jobs[job_id]["progress"] = {
                "leadsFound": result.get("found", 0),
                "leadsNew": result.get("new", 0),
                "percent": 100,
            }
            jobs[job_id]["status"] = "completed"
        except Exception as e:
            logger.exception("Scrape failed")
            jobs[job_id]["output"].append(f"ERROR: {str(e)}")
            jobs[job_id]["status"] = "failed"

    asyncio.create_task(_run())
    return {"jobId": job_id, "status": "running"}


@app.get("/scrape/{job_id}", dependencies=[Depends(verify_api_key)])
async def get_scrape_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    j = jobs[job_id]
    return {
        "jobId": job_id,
        "status": j["status"],
        "output": j["output"],
        "params": j["params"],
        "startedAt": j["started_at"],
        "progress": j["progress"],
    }


@app.get("/scrape", dependencies=[Depends(verify_api_key)])
async def list_scrape_jobs():
    return {
        "jobs": [
            {
                "jobId": jid,
                "status": j["status"],
                "params": j["params"],
                "startedAt": j["started_at"],
                "outputLines": len(j["output"]),
            }
            for jid, j in jobs.items()
        ]
    }


# ---------------------------------------------------------------------------
# Enrich endpoints
# ---------------------------------------------------------------------------

@app.post("/enrich", dependencies=[Depends(verify_api_key)])
async def start_enrich(req: EnrichRequest):
    if enrich_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Enrichment already running")

    enrich_state["status"] = "running"
    enrich_state["output"] = []
    enrich_state["progress"] = {"current": 0, "total": 0, "percent": 0, "lastBusiness": ""}
    enrich_state["limit"] = req.limit
    enrich_state["started_at"] = datetime.now(timezone.utc).isoformat()

    async def _run():
        try:
            engine = ScraperEngine()
            enrich_state["output"].append(f"Starting enrichment of up to {req.limit} leads...")
            result = await engine.enrich_only(limit=req.limit)
            enrich_state["output"].append(
                f"Total: {result.get('total', 0)} | "
                f"Success: {result.get('success', 0)} | "
                f"Failed: {result.get('failed', 0)}"
            )
            enrich_state["progress"] = {
                "current": result.get("success", 0),
                "total": result.get("total", 0),
                "percent": 100,
                "lastBusiness": "",
            }
            enrich_state["status"] = "completed"
        except Exception as e:
            logger.exception("Enrichment failed")
            enrich_state["output"].append(f"ERROR: {str(e)}")
            enrich_state["status"] = "failed"

    asyncio.create_task(_run())
    return {"status": "running", "limit": req.limit}


@app.get("/enrich", dependencies=[Depends(verify_api_key)])
async def get_enrich_status():
    return {
        "status": enrich_state["status"],
        "output": enrich_state.get("output", []),
        "limit": enrich_state.get("limit", 0),
        "progress": enrich_state.get("progress", {}),
        "startedAt": enrich_state.get("started_at", ""),
    }


# ---------------------------------------------------------------------------
# Enrich specific leads (single + bulk)
# ---------------------------------------------------------------------------

@app.post("/enrich/leads", dependencies=[Depends(verify_api_key)])
async def enrich_specific_leads(req: EnrichLeadsRequest):
    """Enrich specific leads by IDs (supports single or bulk)."""
    if not req.lead_ids:
        raise HTTPException(status_code=400, detail="lead_ids is required")

    async def _run():
        try:
            engine = ScraperEngine()
            if len(req.lead_ids) == 1:
                result = await engine.enrich_single(req.lead_ids[0])
            else:
                result = await engine.enrich_multiple(req.lead_ids)
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.exception("Lead enrichment failed")
            raise HTTPException(status_code=500, detail=str(e))

    result = await _run()
    return {"status": "completed", "result": result}


# ---------------------------------------------------------------------------
# Re-enrich endpoints
# ---------------------------------------------------------------------------

re_enrich_state: dict = {"status": "idle", "output": [], "progress": {}}


@app.post("/re-enrich", dependencies=[Depends(verify_api_key)])
async def start_re_enrich(req: ReEnrichRequest):
    if re_enrich_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Re-enrichment already running")

    re_enrich_state["status"] = "running"
    re_enrich_state["output"] = []
    re_enrich_state["progress"] = {"current": 0, "total": 0, "percent": 0}
    re_enrich_state["started_at"] = datetime.now(timezone.utc).isoformat()

    async def _run():
        try:
            engine = ScraperEngine()
            re_enrich_state["output"].append(
                f"Re-enriching leads older than {req.days} days (limit: {req.limit})..."
            )
            result = await engine.re_enrich(stale_days=req.days, limit=req.limit)
            re_enrich_state["output"].append(
                f"Stale found: {result.get('stale_found', 0)} | "
                f"Success: {result.get('success', 0)} | "
                f"Failed: {result.get('failed', 0)}"
            )
            re_enrich_state["progress"] = {
                "current": result.get("success", 0),
                "total": result.get("stale_found", 0),
                "percent": 100,
            }
            re_enrich_state["status"] = "completed"
        except Exception as e:
            logger.exception("Re-enrichment failed")
            re_enrich_state["output"].append(f"ERROR: {str(e)}")
            re_enrich_state["status"] = "failed"

    asyncio.create_task(_run())
    return {"status": "running", "days": req.days, "limit": req.limit}


@app.get("/re-enrich", dependencies=[Depends(verify_api_key)])
async def get_re_enrich_status():
    return {
        "status": re_enrich_state["status"],
        "output": re_enrich_state.get("output", []),
        "progress": re_enrich_state.get("progress", {}),
        "startedAt": re_enrich_state.get("started_at", ""),
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting LeadScraper API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
