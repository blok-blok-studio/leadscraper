"""Better Business Bureau (BBB) scraper for US local business leads."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class BBBScraper(BaseScraper):
    """Scrape business listings from BBB.org."""

    SOURCE_NAME = "bbb"
    BASE_URL = "https://www.bbb.org"

    def search(self, category: str, location: str, max_pages: int = 5) -> list[dict]:
        leads = []
        for page in range(1, max_pages + 1):
            try:
                page_leads = self._scrape_page(category, location, page)
                if not page_leads:
                    break
                leads.extend(page_leads)
                logger.debug(f"[BBB] Page {page}: {len(page_leads)} listings")
            except Exception as e:
                logger.error(f"[BBB] Error on page {page}: {e}")
                break
        return leads

    def _scrape_page(self, category: str, location: str, page: int) -> list[dict]:
        """Scrape a single BBB search results page."""
        search_query = quote_plus(category)
        location_query = quote_plus(location)
        url = f"{self.BASE_URL}/search"
        params = {
            "find_country": "US",
            "find_text": search_query,
            "find_loc": location_query,
            "page": page,
        }

        soup = self.http.get_soup(url, params=params)
        results = soup.select("div.result-item, li.result-item, div[data-testid='result']")

        if not results:
            results = soup.select("a[class*='result'], div[class*='search-result']")

        leads = []
        for card in results:
            try:
                lead = self._parse_listing(card)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"[BBB] Failed to parse listing: {e}")
                continue

        return leads

    def _parse_listing(self, card) -> dict | None:
        """Parse a single BBB business listing."""
        # Business name
        name_el = card.select_one("h3 a, .result-name a, a[class*='business-name']")
        if not name_el:
            name_el = card.select_one("h3, .bds-h4, [class*='name']")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        # Phone
        phone = None
        phone_el = card.select_one("a[href^='tel:'], .result-phone, [class*='phone']")
        if phone_el:
            phone = phone_el.get_text(strip=True)
            if not phone and phone_el.get("href"):
                phone = phone_el["href"].replace("tel:", "")

        # Address
        address = ""
        city = ""
        state = ""
        zip_code = ""

        addr_el = card.select_one(".result-address, address, [class*='address']")
        if addr_el:
            addr_text = addr_el.get_text(separator=" ", strip=True)
            parts = [p.strip() for p in addr_text.split(",")]
            if len(parts) >= 2:
                address = parts[0]
                city = parts[1].strip() if len(parts) > 1 else ""
                if len(parts) > 2:
                    state_zip = parts[2].strip()
                    match = re.match(r"([A-Z]{2})\s*(\d{5})?", state_zip)
                    if match:
                        state = match.group(1)
                        zip_code = match.group(2) or ""

        # BBB Rating
        bbb_rating = None
        bbb_accredited = False
        rating_el = card.select_one(".result-rating, [class*='rating'], .bds-rating")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            match = re.search(r"([A-F][+-]?)", rating_text)
            if match:
                bbb_rating = match.group(1)

        accred_el = card.select_one("[class*='accredited'], .ab-seal")
        if accred_el:
            bbb_accredited = True

        # Website
        website = None
        web_el = card.select_one("a[href*='http']:not([href*='bbb.org'])")
        if web_el:
            website = web_el.get("href")

        # Source URL
        source_url = ""
        link_el = card.select_one("h3 a, .result-name a")
        if link_el and link_el.get("href"):
            href = link_el["href"]
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Category
        cat_el = card.select_one(".result-category, [class*='category']")
        category_text = cat_el.get_text(strip=True) if cat_el else ""

        return {
            "business_name": name,
            "phone": phone,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "website": website,
            "category": category_text,
            "bbb_rating": bbb_rating,
            "bbb_accredited": bbb_accredited,
            "source_url": source_url,
        }
