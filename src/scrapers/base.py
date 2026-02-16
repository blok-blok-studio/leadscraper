"""Base scraper class that all source scrapers inherit from."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.scrapers.http_client import ScraperHttpClient
from src.utils.cleaning import clean_lead_data

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for lead scrapers."""

    SOURCE_NAME = "base"

    def __init__(self):
        self.http = ScraperHttpClient()

    @abstractmethod
    def search(self, category: str, location: str, max_pages: int = 5) -> list[dict]:
        """
        Search for businesses in a category and location.
        Returns a list of raw lead dicts.
        """
        pass

    def scrape(self, category: str, location: str, max_pages: int = 5) -> list[dict]:
        """Search and clean results."""
        logger.info(f"[{self.SOURCE_NAME}] Scraping '{category}' in '{location}'")
        raw_leads = self.search(category, location, max_pages)
        cleaned = []
        for lead in raw_leads:
            lead["source"] = self.SOURCE_NAME
            lead["country"] = "US"
            cleaned_lead = clean_lead_data(lead)
            if cleaned_lead:
                cleaned.append(cleaned_lead)
        logger.info(
            f"[{self.SOURCE_NAME}] Found {len(raw_leads)} raw, {len(cleaned)} cleaned"
        )
        return cleaned

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
