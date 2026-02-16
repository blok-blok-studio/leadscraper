"""YellowPages.com scraper for US local business leads."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class YellowPagesScraper(BaseScraper):
    """Scrape business listings from YellowPages.com."""

    SOURCE_NAME = "yellowpages"
    BASE_URL = "https://www.yellowpages.com"

    def search(self, category: str, location: str, max_pages: int = 5) -> list[dict]:
        leads = []
        for page in range(1, max_pages + 1):
            try:
                page_leads = self._scrape_page(category, location, page)
                if not page_leads:
                    break
                leads.extend(page_leads)
                logger.debug(
                    f"[YellowPages] Page {page}: {len(page_leads)} listings"
                )
            except Exception as e:
                logger.error(f"[YellowPages] Error on page {page}: {e}")
                break
        return leads

    def _scrape_page(self, category: str, location: str, page: int) -> list[dict]:
        """Scrape a single results page."""
        url = f"{self.BASE_URL}/search"
        params = {
            "search_terms": category,
            "geo_location_terms": location,
            "page": page,
        }

        soup = self.http.get_soup(url, params=params)
        results = soup.select("div.result")

        if not results:
            results = soup.select("div.search-results div.v-card")

        leads = []
        for card in results:
            try:
                lead = self._parse_listing(card)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"[YellowPages] Failed to parse listing: {e}")
                continue

        return leads

    def _parse_listing(self, card) -> dict | None:
        """Parse a single business listing card."""
        # Business name
        name_el = card.select_one("a.business-name, h2.n a, .info-section h2 a")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)

        # Phone
        phone_el = card.select_one("div.phones, .phone, .info-section .phone")
        phone = phone_el.get_text(strip=True) if phone_el else None

        # Address
        address = ""
        city = ""
        state = ""
        zip_code = ""

        street_el = card.select_one("div.street-address, .adr .street-address")
        if street_el:
            address = street_el.get_text(strip=True)

        locality_el = card.select_one("div.locality, .adr .locality")
        if locality_el:
            loc_text = locality_el.get_text(strip=True)
            # Parse "City, ST ZIP"
            match = re.match(r"(.+?),\s*([A-Z]{2})\s*(\d{5})?", loc_text)
            if match:
                city = match.group(1)
                state = match.group(2)
                zip_code = match.group(3) or ""

        # Website
        website = None
        website_el = card.select_one("a.track-visit-website, a[href*='website']")
        if website_el:
            website = website_el.get("href", "")
            if website.startswith("/"):
                website = None

        # Category
        categories_el = card.select_one("div.categories, .info-section .categories")
        category_text = categories_el.get_text(strip=True) if categories_el else ""

        # Source URL
        link_el = card.select_one("a.business-name, h2.n a")
        source_url = ""
        if link_el and link_el.get("href"):
            href = link_el["href"]
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Rating
        rating = None
        rating_el = card.select_one("div.ratings .result-rating, .rating-count")
        if rating_el:
            rating_class = rating_el.get("class", [])
            for cls in rating_class:
                match = re.search(r"(\d+)", cls)
                if match:
                    rating = int(match.group(1)) / 2  # Convert to 5-star scale
                    break

        # Years in business
        year_established = None
        years_el = card.select_one(".years-in-business .count, .yib")
        if years_el:
            try:
                years = int(re.sub(r"\D", "", years_el.get_text()))
                from datetime import datetime
                year_established = datetime.now().year - years
            except (ValueError, TypeError):
                pass

        return {
            "business_name": name,
            "phone": phone,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "website": website,
            "category": category_text,
            "source_url": source_url,
            "year_established": year_established,
        }
