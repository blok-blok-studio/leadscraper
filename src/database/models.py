"""SQLAlchemy models for the lead scraper database."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Lead(Base):
    """Core lead record — a US local business."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Basic info
    business_name = Column(String(500), nullable=False)
    phone = Column(String(20), index=True)
    email = Column(String(255), index=True)
    website = Column(String(500))
    address = Column(String(500))
    city = Column(String(100), index=True)
    state = Column(String(2), index=True)
    zip_code = Column(String(10))
    country = Column(String(2), default="US")

    # Industry / category
    category = Column(String(200), index=True)
    subcategory = Column(String(200))
    industry_tags = Column(ARRAY(String), default=[])

    # Owner / decision maker
    owner_name = Column(String(255))
    owner_title = Column(String(200))
    owner_email = Column(String(255))
    owner_phone = Column(String(20))
    owner_linkedin = Column(String(500))

    # Business details
    employee_count = Column(String(50))  # "1-10", "11-50", etc.
    annual_revenue_estimate = Column(String(100))
    year_established = Column(Integer)
    business_type = Column(String(100))  # LLC, Corp, Sole Prop, etc.

    # Online presence
    facebook_url = Column(String(500))
    instagram_url = Column(String(500))
    twitter_url = Column(String(500))
    linkedin_url = Column(String(500))
    youtube_url = Column(String(500))
    tiktok_url = Column(String(500))

    # Tech stack (from website analysis)
    tech_stack = Column(JSONB, default={})
    has_website = Column(Boolean, default=False)
    website_platform = Column(String(100))  # WordPress, Shopify, Wix, etc.
    has_ssl = Column(Boolean)
    mobile_friendly = Column(Boolean)

    # Reviews / ratings
    google_rating = Column(Float)
    google_review_count = Column(Integer)
    yelp_rating = Column(Float)
    yelp_review_count = Column(Integer)
    bbb_rating = Column(String(10))
    bbb_accredited = Column(Boolean)

    # Ad spend indicators
    runs_google_ads = Column(Boolean)
    runs_facebook_ads = Column(Boolean)
    has_google_business_profile = Column(Boolean)

    # Meta
    source = Column(String(100), nullable=False)  # yellowpages, bbb, yelp
    source_url = Column(String(1000))
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    enriched_at = Column(DateTime)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_enriched = Column(Boolean, default=False)
    enrichment_errors = Column(Text)
    quality_score = Column(Integer, default=0)  # 0-100

    __table_args__ = (
        UniqueConstraint("business_name", "address", "city", "state", name="uq_lead_identity"),
        Index("ix_leads_location", "state", "city", "zip_code"),
        Index("ix_leads_quality", "quality_score", "is_enriched"),
    )

    def __repr__(self):
        return f"<Lead(id={self.id}, name='{self.business_name}', city='{self.city}', state='{self.state}')>"


class ScrapeJob(Base):
    """Tracks individual scraping runs."""

    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), default="running")  # running, completed, failed
    source = Column(String(100))
    category = Column(String(200))
    location = Column(String(200))
    leads_found = Column(Integer, default=0)
    leads_new = Column(Integer, default=0)
    leads_updated = Column(Integer, default=0)
    leads_skipped = Column(Integer, default=0)
    errors = Column(Text)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    def __repr__(self):
        return f"<ScrapeJob(id={self.id}, status='{self.status}', source='{self.source}')>"
