"""Core scraping engine — orchestrates scrapers, enrichment, and database writes."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

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

        scraper = None
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
        finally:
            # Close scraper to free Playwright browser resources
            if scraper:
                try:
                    scraper.close()
                except Exception:
                    pass

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
        """Scrape a single source/category/location, then auto-enrich new leads."""
        result = await self._scrape_single(source, category, location, max_pages)

        # Auto-enrich the newly scraped leads
        enrichment_config = self.config.get("enrichment", {})
        if enrichment_config.get("enabled", True) and result.get("new", 0) > 0:
            logger.info(f"Auto-enriching {result['new']} new leads...")
            enriched = await self._run_enrichment(enrichment_config)
            result["enriched"] = enriched

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

    async def enrich_single(self, lead_id: int) -> dict:
        """Enrich a single lead by ID."""
        enrichment_config = self.config.get("enrichment", {})
        modules = enrichment_config.get("modules", [])
        db = await get_client()

        lead = await db.lead.find_unique(where={"id": lead_id})
        if not lead:
            await disconnect()
            raise ValueError(f"Lead {lead_id} not found")

        # Reset enrichment so pipeline treats it fresh
        await db.lead.update(
            where={"id": lead_id},
            data={"isEnriched": False},
        )
        lead = await db.lead.find_unique(where={"id": lead_id})

        with EnrichmentPipeline(enabled_modules=modules) as pipeline:
            updated = await pipeline.enrich_lead(lead, db)

        await disconnect()
        return {
            "id": lead_id,
            "businessName": updated.businessName,
            "qualityScore": updated.qualityScore,
            "icpScore": updated.icpScore,
            "isEnriched": updated.isEnriched,
        }

    async def enrich_multiple(self, lead_ids: list[int]) -> dict:
        """Enrich multiple leads by IDs."""
        enrichment_config = self.config.get("enrichment", {})
        modules = enrichment_config.get("modules", [])
        db = await get_client()

        # Reset enrichment status
        await db.lead.update_many(
            where={"id": {"in": lead_ids}},
            data={"isEnriched": False},
        )

        leads = await db.lead.find_many(where={"id": {"in": lead_ids}})
        if not leads:
            await disconnect()
            return {"total": 0, "success": 0, "failed": 0}

        with EnrichmentPipeline(enabled_modules=modules) as pipeline:
            results = await pipeline.enrich_batch(leads, db)

        await disconnect()
        return results

    async def re_enrich(self, stale_days: int = 30, limit: int = 50) -> dict:
        """Re-enrich stale leads that were enriched more than stale_days ago.

        Resets isEnriched=False on stale leads, then runs normal enrichment.
        This refreshes data that may have changed (new phone, new website, etc.).
        """
        enrichment_config = self.config.get("enrichment", {})
        modules = enrichment_config.get("modules", [])
        db = await get_client()

        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)

        # Find stale leads: enriched before the cutoff date
        stale_leads = await db.lead.find_many(
            where={
                "isEnriched": True,
                "OR": [
                    {"lastEnrichedAt": {"lt": cutoff}},
                    {"lastEnrichedAt": None, "enrichedAt": {"lt": cutoff}},
                ],
            },
            order={"enrichedAt": "asc"},
            take=limit,
        )

        if not stale_leads:
            logger.info("No stale leads to re-enrich")
            await disconnect()
            return {"total": 0, "success": 0, "failed": 0, "stale_found": 0}

        logger.info(f"Found {len(stale_leads)} stale leads (>{stale_days} days old)")

        # Reset enrichment status so pipeline treats them as fresh
        stale_ids = [lead.id for lead in stale_leads]
        await db.lead.update_many(
            where={"id": {"in": stale_ids}},
            data={"isEnriched": False},
        )
        logger.info(f"Reset {len(stale_ids)} leads for re-enrichment")

        # Fetch them fresh (with isEnriched=False)
        leads_to_enrich = await db.lead.find_many(
            where={"id": {"in": stale_ids}},
        )

        with EnrichmentPipeline(enabled_modules=modules) as pipeline:
            results = await pipeline.enrich_batch(leads_to_enrich, db)

        results["stale_found"] = len(stale_leads)
        await disconnect()
        return results
