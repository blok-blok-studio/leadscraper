"""Data access layer for lead operations using Prisma."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from prisma import Prisma
from prisma.models import Lead, ScrapeJob

from src.database.models import to_prisma_data

logger = logging.getLogger(__name__)


class LeadRepository:
    """CRUD operations for leads."""

    def __init__(self, client: Prisma):
        self.db = client

    async def upsert_lead(self, lead_data: dict) -> tuple:
        """Insert or update a lead. Returns (lead, is_new)."""
        existing = await self._find_duplicate(lead_data)
        prisma_data = to_prisma_data(lead_data)

        if existing:
            # Update existing lead with new data
            update_data = {k: v for k, v in prisma_data.items() if v is not None}
            update_data.pop("businessName", None)  # Don't overwrite name
            lead = await self.db.lead.update(
                where={"id": existing.id},
                data=update_data,
            )
            return lead, False

        lead = await self.db.lead.create(data=prisma_data)
        return lead, True

    async def _find_duplicate(self, lead_data: dict):
        """Check for duplicate lead by phone, email, or name+address."""
        phone = lead_data.get("phone")
        email = lead_data.get("email")
        name = lead_data.get("business_name")
        address = lead_data.get("address")
        city = lead_data.get("city")
        state = lead_data.get("state")

        if phone:
            match = await self.db.lead.find_first(where={"phone": phone})
            if match:
                return match

        if email:
            match = await self.db.lead.find_first(where={"email": email})
            if match:
                return match

        if name and address and city and state:
            match = await self.db.lead.find_first(
                where={
                    "businessName": {"equals": name, "mode": "insensitive"},
                    "address": {"equals": address, "mode": "insensitive"},
                    "city": {"equals": city, "mode": "insensitive"},
                    "state": state.upper(),
                }
            )
            if match:
                return match

        return None

    async def get_unenriched_leads(self, limit: int = 100):
        """Get leads that haven't been enriched yet."""
        return await self.db.lead.find_many(
            where={"isEnriched": False},
            order={"scrapedAt": "desc"},
            take=limit,
        )

    async def get_leads_by_location(self, state: str, city: str = None):
        """Get all leads for a given state/city."""
        where = {"state": state.upper()}
        if city:
            where["city"] = {"equals": city, "mode": "insensitive"}
        return await self.db.lead.find_many(where=where)

    async def get_leads_by_category(self, category: str):
        """Get all leads for a given category."""
        return await self.db.lead.find_many(
            where={"category": {"equals": category, "mode": "insensitive"}}
        )

    async def get_lead_count(self) -> int:
        """Get total number of leads."""
        return await self.db.lead.count()

    async def get_stats(self) -> dict:
        """Get summary statistics."""
        total = await self.db.lead.count()
        enriched = await self.db.lead.count(where={"isEnriched": True})

        # Top states via raw query
        by_state = await self.db.query_raw(
            """
            SELECT state, COUNT(*)::int as count
            FROM leads
            WHERE state IS NOT NULL
            GROUP BY state
            ORDER BY count DESC
            LIMIT 10
            """
        )

        # Top categories via raw query
        by_category = await self.db.query_raw(
            """
            SELECT category, COUNT(*)::int as count
            FROM leads
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
            """
        )

        # Average quality score
        avg_result = await self.db.query_raw(
            "SELECT COALESCE(AVG(quality_score), 0)::float as avg_score FROM leads"
        )
        avg_quality = avg_result[0]["avg_score"] if avg_result else 0

        return {
            "total_leads": total,
            "enriched_leads": enriched,
            "unenriched_leads": total - enriched,
            "avg_quality_score": round(float(avg_quality), 1),
            "top_states": [{"state": r["state"], "count": r["count"]} for r in by_state],
            "top_categories": [{"category": r["category"], "count": r["count"]} for r in by_category],
        }

    async def update_lead(self, lead_id: int, data: dict):
        """Update a lead by ID with a dict of camelCase fields."""
        return await self.db.lead.update(where={"id": lead_id}, data=data)


class JobRepository:
    """CRUD operations for scrape jobs."""

    def __init__(self, client: Prisma):
        self.db = client

    async def create_job(self, source: str, category: str, location: str):
        """Create a new scrape job record."""
        return await self.db.scrapejob.create(
            data={
                "source": source,
                "category": category,
                "location": location,
                "status": "running",
            }
        )

    async def complete_job(self, job_id: int, leads_found: int, leads_new: int,
                           leads_updated: int, leads_skipped: int, errors: str = None):
        """Mark a job as completed."""
        now = datetime.now(timezone.utc)
        job = await self.db.scrapejob.find_unique(where={"id": job_id})
        duration = (now - job.startedAt).total_seconds() if job else 0

        return await self.db.scrapejob.update(
            where={"id": job_id},
            data={
                "status": "completed",
                "leadsFound": leads_found,
                "leadsNew": leads_new,
                "leadsUpdated": leads_updated,
                "leadsSkipped": leads_skipped,
                "errors": errors,
                "completedAt": now,
                "durationSeconds": duration,
            },
        )

    async def fail_job(self, job_id: int, error: str):
        """Mark a job as failed."""
        now = datetime.now(timezone.utc)
        job = await self.db.scrapejob.find_unique(where={"id": job_id})
        duration = (now - job.startedAt).total_seconds() if job else 0

        return await self.db.scrapejob.update(
            where={"id": job_id},
            data={
                "status": "failed",
                "errors": error,
                "completedAt": now,
                "durationSeconds": duration,
            },
        )
