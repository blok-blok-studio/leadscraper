"""Scraper registry — maps source names to scraper classes."""

from __future__ import annotations

from src.scrapers.base import BaseScraper
from src.scrapers.yellowpages import YellowPagesScraper
from src.scrapers.bbb import BBBScraper
from src.scrapers.yelp import YelpScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    "yellowpages": YellowPagesScraper,
    "bbb": BBBScraper,
    "yelp": YelpScraper,
}


def get_scraper(source_name: str) -> BaseScraper:
    """Get a scraper instance by source name."""
    scraper_cls = SCRAPERS.get(source_name.lower())
    if not scraper_cls:
        available = ", ".join(SCRAPERS.keys())
        raise ValueError(f"Unknown source '{source_name}'. Available: {available}")
    return scraper_cls()


def get_all_scrapers() -> list[BaseScraper]:
    """Get instances of all registered scrapers."""
    return [cls() for cls in SCRAPERS.values()]
