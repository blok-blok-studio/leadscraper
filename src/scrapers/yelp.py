"""Yelp.com scraper for US local business leads."""

from __future__ import annotations

import logging
import re
import json

from bs4 import BeautifulSoup

from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class YelpScraper(BaseScraper):
    """Scrape business listings from Yelp.com."""

    SOURCE_NAME = "yelp"
    BASE_URL = "https://www.yelp.com"

    def search(self, category: str, location: str, max_pages: int = 5) -> list[dict]:
        leads = []
        for page in range(max_pages):
            try:
                start = page * 10
                page_leads = self._scrape_page(category, location, start)
                if not page_leads:
                    break
                leads.extend(page_leads)
                logger.debug(
                    f"[Yelp] Page {page + 1}: {len(page_leads)} listings"
                )
            except Exception as e:
                logger.error(f"[Yelp] Error on page {page + 1}: {e}")
                break
        return leads

    def _scrape_page(self, category: str, location: str, start: int) -> list[dict]:
        """Scrape a single Yelp search results page."""
        url = f"{self.BASE_URL}/search"
        params = {
            "find_desc": category,
            "find_loc": location,
            "start": start,
        }

        soup = self.http.get_soup(url, params=params)

        # Try to extract from JSON-LD structured data first
        leads = self._extract_from_jsonld(soup)
        if leads:
            return leads

        # Fallback to HTML parsing
        return self._extract_from_html(soup)

    def _extract_from_jsonld(self, soup: BeautifulSoup) -> list[dict]:
        """Try to extract data from JSON-LD script tags."""
        leads = []
        scripts = soup.select('script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        lead = self._parse_jsonld_item(item)
                        if lead:
                            leads.append(lead)
                elif isinstance(data, dict):
                    if data.get("@type") == "ItemList":
                        for item in data.get("itemListElement", []):
                            lead = self._parse_jsonld_item(item.get("item", item))
                            if lead:
                                leads.append(lead)
                    else:
                        lead = self._parse_jsonld_item(data)
                        if lead:
                            leads.append(lead)
            except (json.JSONDecodeError, AttributeError):
                continue
        return leads

    def _parse_jsonld_item(self, item: dict) -> dict | None:
        """Parse a JSON-LD LocalBusiness item."""
        if not isinstance(item, dict):
            return None
        item_type = item.get("@type", "")
        if "Business" not in item_type and "Organization" not in item_type:
            return None

        name = item.get("name")
        if not name:
            return None

        address_data = item.get("address", {})
        phone = item.get("telephone")
        rating_data = item.get("aggregateRating", {})

        return {
            "business_name": name,
            "phone": phone,
            "address": address_data.get("streetAddress", ""),
            "city": address_data.get("addressLocality", ""),
            "state": address_data.get("addressRegion", ""),
            "zip_code": address_data.get("postalCode", ""),
            "website": item.get("url"),
            "yelp_rating": float(rating_data.get("ratingValue", 0)) or None,
            "yelp_review_count": int(rating_data.get("reviewCount", 0)) or None,
            "source_url": item.get("url", ""),
        }

    def _extract_from_html(self, soup: BeautifulSoup) -> list[dict]:
        """Fallback HTML parsing for Yelp results."""
        leads = []

        # Yelp uses various container class patterns
        containers = soup.select(
            '[class*="container"] [class*="searchResult"], '
            'li[class*="result"], '
            'div[data-testid*="serp-ia-card"]'
        )

        for card in containers:
            try:
                lead = self._parse_html_listing(card)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"[Yelp] Failed to parse HTML listing: {e}")
                continue

        return leads

    def _parse_html_listing(self, card) -> dict | None:
        """Parse a single Yelp listing from HTML."""
        # Business name
        name_el = card.select_one(
            'a[class*="businessName"], h3 a, [class*="heading"] a'
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        # Strip leading numbers like "1. " or "2. "
        name = re.sub(r"^\d+\.\s*", "", name)
        if not name:
            return None

        # Phone
        phone = None
        phone_el = card.select_one('[class*="phone"], a[href^="tel:"]')
        if phone_el:
            phone = phone_el.get_text(strip=True)

        # Address
        address = ""
        city = ""
        state = ""
        zip_code = ""
        addr_el = card.select_one('[class*="address"], address')
        if addr_el:
            addr_text = addr_el.get_text(separator=", ", strip=True)
            # Try "123 Main St, City, ST 12345"
            match = re.match(
                r"(.+?),\s*(.+?),\s*([A-Z]{2})\s*(\d{5})?", addr_text
            )
            if match:
                address = match.group(1)
                city = match.group(2)
                state = match.group(3)
                zip_code = match.group(4) or ""

        # Rating
        yelp_rating = None
        rating_el = card.select_one('[class*="rating"], [aria-label*="rating"]')
        if rating_el:
            label = rating_el.get("aria-label", "")
            match = re.search(r"([\d.]+)\s*star", label)
            if match:
                yelp_rating = float(match.group(1))

        # Review count
        yelp_review_count = None
        review_el = card.select_one('[class*="reviewCount"], [class*="review"]')
        if review_el:
            text = review_el.get_text()
            match = re.search(r"(\d+)", text)
            if match:
                yelp_review_count = int(match.group(1))

        # Category
        category = ""
        cat_el = card.select_one('[class*="category"], [class*="tag"]')
        if cat_el:
            category = cat_el.get_text(strip=True)

        # Source URL
        source_url = ""
        if name_el.get("href"):
            href = name_el["href"]
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        return {
            "business_name": name,
            "phone": phone,
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "category": category,
            "yelp_rating": yelp_rating,
            "yelp_review_count": yelp_review_count,
            "source_url": source_url,
        }
