"""Core scraping engine — orchestrates scrapers, enrichment, and database writes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.config import load_config
from src.database.connection import get_client, disconnect
from src.database.repository import LeadRepository, JobRepository
from src.scrapers.registry import get_scraper
from src.enrichment.pipeline import EnrichmentPipeline
from src.utils.us_locations import get_locations

logger = logging.getLogger(__name__)


class ScraperEngine:
    """Main engine that ties together scraping, enrichment, and storage."""

    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)

    async def run(self) -> dict:
        """Run the full scraping pipeline based on config."""
        targeting = self.config["targeting"]
        scraping = self.config["scraping"]
        enrichment_config = self.config.get("enrichment", {})

        sources = scraping.get("sources", ["yellowpages"])
        categories = targeting.get("categories", [])
        max_pages = scraping.get("max_pages_per_search", 5)

        locations = get_locations(
            states=targeting.get("states", []),
            cities=targeting.get("cities", []),
        )

        total_stats = {
            "total_found": 0,
            "total_new": 0,
            "total_updated": 0,
            "total_skipped": 0,
            "total_enriched": 0,
            "errors": [],
        }

        for source_name in sources:
            for category in categories:
                for location in locations:
                    stats = await self._scrape_single(
                        source_name, category, location, max_pages
                    )
                    total_stats["total_found"] += stats.get("found", 0)
                    total_stats["total_new"] += stats.get("new", 0)
                    total_stats["total_updated"] += stats.get("updated", 0)
                    total_stats["total_skipped"] += stats.get("skipped", 0)
                    if stats.get("error"):
                        total_stats["errors"].append(stats["error"])

        # Run enrichment if enabled
        if enrichment_config.get("enabled", True):
            enriched = await self._run_enrichment(enrichment_config)
            total_stats["total_enriched"] = enriched

        await disconnect()
        logger.info(f"Scraping complete: {total_stats}")
        return total_stats

    async def _scrape_single(
        self, source_name: str, category: str, location: str, max_pages: int
    ) -> dict:
        """Scrape a single source/category/location combination."""
        db = await get_client()
        lead_repo = LeadRepository(db)
        job_repo = JobRepository(db)

        job = await job_repo.create_job(source_name, category, location)

        stats = {"found": 0, "new": 0, "updated": 0, "skipped": 0, "error": None}

        try:
            scraper = get_scraper(source_name)
            leads = scraper.scrape(category, location, max_pages)
            stats["found"] = len(leads)

            for lead_data in leads:
                try:
                    lead, is_new = await lead_repo.upsert_lead(lead_data)
                    if is_new:
                        stats["new"] += 1
                    else:
                        stats["updated"] += 1
                except Exception as e:
                    stats["skipped"] += 1
                    logger.debug(f"Skipped lead: {e}")

            await job_repo.complete_job(
                job.id, stats["found"], stats["new"],
                stats["updated"], stats["skipped"],
            )

            logger.info(
                f"[{source_name}] {category} in {location}: "
                f"{stats['found']} found, {stats['new']} new, "
                f"{stats['updated']} updated"
            )

        except Exception as e:
            error_msg = f"[{source_name}] {category} in {location}: {str(e)}"
            logger.error(error_msg)
            stats["error"] = error_msg
            await job_repo.fail_job(job.id, str(e))

        return stats

    async def _run_enrichment(self, enrichment_config: dict) -> int:
        """Run enrichment on unenriched leads."""
        modules = enrichment_config.get("modules", [])
        db = await get_client()
        lead_repo = LeadRepository(db)

        unenriched = await lead_repo.get_unenriched_leads(limit=200)
        if not unenriched:
            logger.info("No leads to enrich")
            return 0

        logger.info(f"Enriching {len(unenriched)} leads...")

        with EnrichmentPipeline(enabled_modules=modules) as pipeline:
            results = await pipeline.enrich_batch(unenriched, db)

        return results["success"]

    async def scrape_single_source(
        self, source: str, category: str, location: str, max_pages: int = 5
    ) -> dict:
        """Scrape a single source/category/location (for CLI use)."""
        result = await self._scrape_single(source, category, location, max_pages)
        await disconnect()
        return result

    async def enrich_only(self, limit: int = 100) -> dict:
        """Only run enrichment, no scraping."""
        enrichment_config = self.config.get("enrichment", {})
        modules = enrichment_config.get("modules", [])
        db = await get_client()
        lead_repo = LeadRepository(db)

        unenriched = await lead_repo.get_unenriched_leads(limit=limit)
        if not unenriched:
            await disconnect()
            return {"total": 0, "success": 0, "failed": 0}

        with EnrichmentPipeline(enabled_modules=modules) as pipeline:
            results = await pipeline.enrich_batch(unenriched, db)

        await disconnect()
        return results
