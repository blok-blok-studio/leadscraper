"""Enrichment pipeline — runs all enrichment modules on leads with concurrency."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from prisma import Prisma

from src.enrichment.website_discovery import WebsiteDiscoveryEnricher
from src.enrichment.google_intel import GoogleIntelEnricher
from src.enrichment.deep_contact import DeepContactEnricher
from src.enrichment.email_discovery import EmailDiscoveryEnricher
from src.enrichment.phone_discovery import PhoneDiscoveryEnricher
from src.enrichment.tech_stack import TechStackEnricher
from src.enrichment.social_media import SocialMediaEnricher
from src.enrichment.contact_enrichment import ContactEnricher
from src.enrichment.reviews import ReviewsEnricher
from src.enrichment.email_verification import EmailVerificationEnricher
from src.enrichment.icp_scoring import ICPScoringEnricher
from src.utils.cleaning import calculate_quality_score
from src.database.models import to_snake_dict, to_prisma_data
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)


def _to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake_str.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# Order matters! Website discovery + google_intel run first so later modules can skip work.
# Phase 1 (sequential): website + google intel → Phase 2: all parallel → Phase 3: verification → Phase 4: scoring
MODULE_MAP = {
    "website_discovery": WebsiteDiscoveryEnricher,
    "google_intel": GoogleIntelEnricher,
    "deep_contact": DeepContactEnricher,
    "email_discovery": EmailDiscoveryEnricher,
    "phone_discovery": PhoneDiscoveryEnricher,
    "website_tech_stack": TechStackEnricher,
    "social_media": SocialMediaEnricher,
    "contact_enrichment": ContactEnricher,
    "reviews_ratings": ReviewsEnricher,
    "email_verification": EmailVerificationEnricher,
    "icp_scoring": ICPScoringEnricher,
}

# Phase 1: Sequential — find website URL + consolidated Google search
PHASE_1_MODULES = ["website_discovery", "google_intel"]

# Phase 2: All independent modules run concurrently (deep_contact now parallel too)
PHASE_2_PARALLEL = [
    "deep_contact", "email_discovery", "phone_discovery",
    "website_tech_stack", "social_media", "contact_enrichment",
    "reviews_ratings",
]

# Phase 3: Email verification (needs emails from phase 2)
PHASE_3_MODULES = ["email_verification"]

# Phase 4: ICP scoring (needs all data)
PHASE_4_MODULES = ["icp_scoring"]


class EnrichmentPipeline:
    """Run enrichment modules on leads and update the database.

    Optimizations:
    - Shared HTTP client across all modules (URL cache eliminates ~60% of requests)
    - Per-domain rate limiting (requests to different domains don't wait)
    - Independent modules run concurrently via thread pool
    - Multiple leads processed in parallel via asyncio.gather
    """

    def __init__(self, enabled_modules: list[str] = None):
        if enabled_modules is None:
            enabled_modules = list(MODULE_MAP.keys())

        # Shared HTTP client — all modules share one so URL cache works
        self._shared_http = ScraperHttpClient()

        # Thread pool for running sync enricher modules concurrently
        self._thread_pool = ThreadPoolExecutor(
            max_workers=6, thread_name_prefix="enricher"
        )

        # Build enricher instances, injecting shared HTTP client
        self._enricher_map: dict[str, object] = {}
        for name in enabled_modules:
            cls = MODULE_MAP.get(name)
            if cls:
                enricher = cls()
                # Override the HTTP client with our shared cached one
                if hasattr(enricher, "http"):
                    enricher.http = self._shared_http
                self._enricher_map[name] = enricher
            else:
                logger.warning(f"Unknown enrichment module: {name}")

        # Keep ordered list for backward compatibility
        self.enrichers = list(self._enricher_map.values())

    def _get_enricher(self, name: str):
        """Get an enricher by module name."""
        return self._enricher_map.get(name)

    def _run_module(self, name: str, lead, errors: list) -> dict:
        """Run a single enrichment module synchronously."""
        enricher = self._get_enricher(name)
        if not enricher:
            return {}
        try:
            result = enricher.safe_enrich(lead)
            return result or {}
        except Exception as e:
            errors.append(f"{name}: {str(e)}")
            return {}

    def _apply_updates(self, lead, updates: dict):
        """Apply accumulated updates to the lead object so subsequent modules see them."""
        for key, value in updates.items():
            camel_key = _to_camel(key)
            if hasattr(lead, camel_key):
                object.__setattr__(lead, camel_key, value)
            elif hasattr(lead, key):
                object.__setattr__(lead, key, value)

    def _modules_to_skip(self, lead) -> set[str]:
        """Determine which modules can be skipped based on existing data.

        After google_intel runs in Phase 1, many fields are already populated.
        Downstream modules check for existing data and short-circuit, but we can
        skip launching them entirely to save thread overhead and avoid any
        residual Google searches.
        """
        skip = set()

        # No website → skip modules that require one
        if not lead.website:
            skip.update(["deep_contact", "website_tech_stack", "social_media"])

        return skip

    async def enrich_lead(self, lead, db: Prisma):
        """Run all enrichment modules on a single lead.

        Uses a phased approach:
          Phase 1: website_discovery + google_intel (sequential — finds URL + bulk data)
          Phase 2: 7 independent modules run concurrently via thread pool
          Phase 3: email_verification (needs emails from phase 2)
          Phase 4: icp_scoring (needs all data)
        """
        errors = []
        updates = {}
        loop = asyncio.get_event_loop()

        # ── Phase 1: Website discovery + Google Intel (sequential) ──
        for mod_name in PHASE_1_MODULES:
            result = self._run_module(mod_name, lead, errors)
            if result:
                updates.update(result)
            self._apply_updates(lead, updates)

        # Determine which modules to skip based on what Phase 1 already found
        skip = self._modules_to_skip(lead)
        if skip:
            logger.debug(f"[Pipeline] Skipping modules for {lead.businessName}: {skip}")

        # ── Phase 2: All independent modules — run concurrently ──
        parallel_tasks = []
        parallel_names = []
        for mod_name in PHASE_2_PARALLEL:
            if mod_name in skip:
                continue
            enricher = self._get_enricher(mod_name)
            if enricher:
                parallel_tasks.append(
                    loop.run_in_executor(self._thread_pool, enricher.safe_enrich, lead)
                )
                parallel_names.append(mod_name)

        if parallel_tasks:
            results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
            for mod_name, result in zip(parallel_names, results):
                if isinstance(result, Exception):
                    errors.append(f"{mod_name}: {str(result)}")
                elif isinstance(result, dict) and result:
                    updates.update(result)

        self._apply_updates(lead, updates)

        # ── Phase 3: Email verification (sequential, needs emails) ──
        for mod_name in PHASE_3_MODULES:
            result = self._run_module(mod_name, lead, errors)
            if result:
                updates.update(result)
        self._apply_updates(lead, updates)

        # ── Phase 4: ICP scoring (sequential, needs everything) ──
        for mod_name in PHASE_4_MODULES:
            result = self._run_module(mod_name, lead, errors)
            if result:
                updates.update(result)

        # ── Save to database ──
        prisma_updates = to_prisma_data(updates)

        # Build a combined dict for quality score calculation
        lead_dict = to_snake_dict(lead)
        lead_dict.update(updates)
        quality_score = calculate_quality_score(lead_dict)

        # Add meta fields
        now = datetime.now(timezone.utc)
        prisma_updates["isEnriched"] = True
        prisma_updates["enrichedAt"] = now
        prisma_updates["lastEnrichedAt"] = now
        prisma_updates["qualityScore"] = quality_score
        if errors:
            prisma_updates["enrichmentErrors"] = "; ".join(errors)

        updated = await db.lead.update(
            where={"id": lead.id},
            data=prisma_updates,
        )

        icp = updates.get("icp_score", 0)
        logger.info(
            f"Enriched: {lead.businessName} | "
            f"Quality: {quality_score} | "
            f"ICP: {icp} | "
            f"Errors: {len(errors)}"
        )
        return updated

    async def _safe_enrich_lead(self, lead, db: Prisma) -> bool:
        """Enrich a single lead with error handling. Returns True on success."""
        try:
            await self.enrich_lead(lead, db)
            return True
        except Exception as e:
            logger.error(f"Failed to enrich {lead.businessName}: {e}")
            return False

    async def enrich_batch(self, leads, db: Prisma) -> dict:
        """Enrich a batch of leads concurrently.

        Processes leads in parallel batches of 5 for ~5x speedup.
        Combined with HTTP caching and parallel modules, total enrichment
        is ~6-8x faster than the original sequential approach.
        """
        total = len(leads)
        success = 0
        failed = 0
        batch_size = 5  # Concurrent leads

        for i in range(0, total, batch_size):
            batch = leads[i:i + batch_size]

            # Clear HTTP cache between batches to free memory
            # (different leads have different websites, cache won't help across leads)
            self._shared_http.clear_cache()

            # Process batch concurrently
            tasks = [self._safe_enrich_lead(lead, db) for lead in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception) or result is False:
                    failed += 1
                else:
                    success += 1

            completed = min(i + batch_size, total)
            logger.info(f"Enrichment progress: {completed}/{total}")

        return {
            "total": total,
            "success": success,
            "failed": failed,
        }

    def close(self):
        """Clean up resources."""
        self._shared_http.close()
        self._thread_pool.shutdown(wait=False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
