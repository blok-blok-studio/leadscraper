"""Data access layer for lead operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.models import Lead, ScrapeJob


class LeadRepository:
    """CRUD operations for leads."""

    def __init__(self, session: Session):
        self.session = session

    def upsert_lead(self, lead_data: dict) -> tuple[Lead, bool]:
        """Insert or update a lead. Returns (lead, is_new)."""
        existing = self._find_duplicate(lead_data)

        if existing:
            for key, value in lead_data.items():
                if value is not None and hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            self.session.flush()
            return existing, False

        lead = Lead(**lead_data)
        self.session.add(lead)
        self.session.flush()
        return lead, True

    def _find_duplicate(self, lead_data: dict) -> Optional[Lead]:
        """Check for duplicate lead by phone, email, or name+address."""
        phone = lead_data.get("phone")
        email = lead_data.get("email")
        name = lead_data.get("business_name")
        address = lead_data.get("address")
        city = lead_data.get("city")
        state = lead_data.get("state")

        if phone:
            match = self.session.query(Lead).filter(Lead.phone == phone).first()
            if match:
                return match

        if email:
            match = self.session.query(Lead).filter(Lead.email == email).first()
            if match:
                return match

        if name and address and city and state:
            match = (
                self.session.query(Lead)
                .filter(
                    and_(
                        func.lower(Lead.business_name) == name.lower(),
                        func.lower(Lead.address) == address.lower(),
                        func.lower(Lead.city) == city.lower(),
                        Lead.state == state.upper(),
                    )
                )
                .first()
            )
            if match:
                return match

        return None

    def get_unenriched_leads(self, limit: int = 100) -> list[Lead]:
        """Get leads that haven't been enriched yet."""
        return (
            self.session.query(Lead)
            .filter(Lead.is_enriched == False)
            .order_by(Lead.scraped_at.desc())
            .limit(limit)
            .all()
        )

    def get_leads_by_location(self, state: str, city: str = None) -> list[Lead]:
        """Get all leads for a given state/city."""
        query = self.session.query(Lead).filter(Lead.state == state.upper())
        if city:
            query = query.filter(func.lower(Lead.city) == city.lower())
        return query.all()

    def get_leads_by_category(self, category: str) -> list[Lead]:
        """Get all leads for a given category."""
        return (
            self.session.query(Lead)
            .filter(func.lower(Lead.category) == category.lower())
            .all()
        )

    def get_lead_count(self) -> int:
        """Get total number of leads."""
        return self.session.query(func.count(Lead.id)).scalar()

    def get_stats(self) -> dict:
        """Get summary statistics."""
        total = self.get_lead_count()
        enriched = (
            self.session.query(func.count(Lead.id))
            .filter(Lead.is_enriched == True)
            .scalar()
        )
        by_state = (
            self.session.query(Lead.state, func.count(Lead.id))
            .group_by(Lead.state)
            .order_by(func.count(Lead.id).desc())
            .limit(10)
            .all()
        )
        by_category = (
            self.session.query(Lead.category, func.count(Lead.id))
            .group_by(Lead.category)
            .order_by(func.count(Lead.id).desc())
            .limit(10)
            .all()
        )
        avg_quality = (
            self.session.query(func.avg(Lead.quality_score)).scalar() or 0
        )

        return {
            "total_leads": total,
            "enriched_leads": enriched,
            "unenriched_leads": total - enriched,
            "avg_quality_score": round(float(avg_quality), 1),
            "top_states": [{"state": s, "count": c} for s, c in by_state],
            "top_categories": [{"category": c, "count": n} for c, n in by_category],
        }


class JobRepository:
    """CRUD operations for scrape jobs."""

    def __init__(self, session: Session):
        self.session = session

    def create_job(self, source: str, category: str, location: str) -> ScrapeJob:
        """Create a new scrape job record."""
        job = ScrapeJob(source=source, category=category, location=location)
        self.session.add(job)
        self.session.flush()
        return job

    def complete_job(self, job: ScrapeJob, leads_found: int, leads_new: int,
                     leads_updated: int, leads_skipped: int, errors: str = None):
        """Mark a job as completed."""
        now = datetime.now(timezone.utc)
        job.status = "completed"
        job.leads_found = leads_found
        job.leads_new = leads_new
        job.leads_updated = leads_updated
        job.leads_skipped = leads_skipped
        job.errors = errors
        job.completed_at = now
        job.duration_seconds = (now - job.started_at).total_seconds()
        self.session.flush()

    def fail_job(self, job: ScrapeJob, error: str):
        """Mark a job as failed."""
        now = datetime.now(timezone.utc)
        job.status = "failed"
        job.errors = error
        job.completed_at = now
        job.duration_seconds = (now - job.started_at).total_seconds()
        self.session.flush()
