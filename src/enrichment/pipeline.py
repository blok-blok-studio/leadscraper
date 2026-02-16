"""Enrichment pipeline — runs all enrichment modules on leads."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.database.models import Lead
from src.enrichment.tech_stack import TechStackEnricher
from src.enrichment.social_media import SocialMediaEnricher
from src.enrichment.contact_enrichment import ContactEnricher
from src.enrichment.reviews import ReviewsEnricher
from src.utils.cleaning import calculate_quality_score

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

    def enrich_lead(self, lead: Lead, session) -> Lead:
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

        # Apply updates to the lead
        for field, value in updates.items():
            if hasattr(lead, field) and value is not None:
                setattr(lead, field, value)

        # Recalculate quality score with enriched data
        lead_dict = {c.name: getattr(lead, c.name) for c in lead.__table__.columns}
        lead.quality_score = calculate_quality_score(lead_dict)

        # Mark as enriched
        lead.is_enriched = True
        lead.enriched_at = datetime.now(timezone.utc)
        if errors:
            lead.enrichment_errors = "; ".join(errors)

        session.commit()

        logger.info(
            f"Enriched: {lead.business_name} | "
            f"Quality: {lead.quality_score} | "
            f"Errors: {len(errors)}"
        )
        return lead

    def enrich_batch(self, leads: list[Lead], session) -> dict:
        """Enrich a batch of leads. Returns summary stats."""
        total = len(leads)
        success = 0
        failed = 0

        for i, lead in enumerate(leads, 1):
            try:
                self.enrich_lead(lead, session)
                success += 1
            except Exception as e:
                failed += 1
                logger.error(f"Failed to enrich {lead.business_name}: {e}")

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
