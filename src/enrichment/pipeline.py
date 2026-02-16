"""Enrichment pipeline — runs all enrichment modules on leads."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from prisma import Prisma

from src.enrichment.tech_stack import TechStackEnricher
from src.enrichment.social_media import SocialMediaEnricher
from src.enrichment.contact_enrichment import ContactEnricher
from src.enrichment.reviews import ReviewsEnricher
from src.utils.cleaning import calculate_quality_score
from src.database.models import to_snake_dict, to_prisma_data

logger = logging.getLogger(__name__)

MODULE_MAP = {
    "website_tech_stack": TechStackEnricher,
    "social_media": SocialMediaEnricher,
    "contact_enrichment": ContactEnricher,
    "reviews_ratings": ReviewsEnricher,
}


class EnrichmentPipeline:
    """Run enrichment modules on leads and update the database."""

    def __init__(self, enabled_modules: list[str] = None):
        if enabled_modules is None:
            enabled_modules = list(MODULE_MAP.keys())

        self.enrichers = []
        for name in enabled_modules:
            cls = MODULE_MAP.get(name)
            if cls:
                self.enrichers.append(cls())
            else:
                logger.warning(f"Unknown enrichment module: {name}")

    async def enrich_lead(self, lead, db: Prisma):
        """Run all enrichment modules on a single lead."""
        errors = []
        updates = {}

        for enricher in self.enrichers:
            try:
                result = enricher.safe_enrich(lead)
                if result:
                    updates.update(result)
            except Exception as e:
                errors.append(f"{enricher.MODULE_NAME}: {str(e)}")

        # Convert snake_case updates to camelCase for Prisma
        prisma_updates = to_prisma_data(updates)

        # Build a combined dict for quality score calculation
        lead_dict = to_snake_dict(lead)
        lead_dict.update(updates)
        quality_score = calculate_quality_score(lead_dict)

        # Add meta fields
        prisma_updates["isEnriched"] = True
        prisma_updates["enrichedAt"] = datetime.now(timezone.utc)
        prisma_updates["qualityScore"] = quality_score
        if errors:
            prisma_updates["enrichmentErrors"] = "; ".join(errors)

        updated = await db.lead.update(
            where={"id": lead.id},
            data=prisma_updates,
        )

        logger.info(
            f"Enriched: {lead.businessName} | "
            f"Quality: {quality_score} | "
            f"Errors: {len(errors)}"
        )
        return updated

    async def enrich_batch(self, leads, db: Prisma) -> dict:
        """Enrich a batch of leads. Returns summary stats."""
        total = len(leads)
        success = 0
        failed = 0

        for i, lead in enumerate(leads, 1):
            try:
                await self.enrich_lead(lead, db)
                success += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to enrich {lead.businessName}: {e}")

            if i % 10 == 0:
                logger.info(f"Enrichment progress: {i}/{total}")

        return {
            "total": total,
            "success": success,
            "failed": failed,
        }

    def close(self):
        for enricher in self.enrichers:
            if hasattr(enricher, "close"):
                enricher.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
