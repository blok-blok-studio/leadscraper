"""Better Business Bureau (BBB) scraper for US local business leads."""

from __future__ import annotations

import logging
import re
import json
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
        """Scrape a single BBB search results page using Playwright."""
        search_query = quote_plus(category)
        location_query = quote_plus(location)
        url = f"{self.BASE_URL}/search"
        params = {
            "find_country": "US",
            "find_text": search_query,
            "find_loc": location_query,
            "page": page,
        }

        # Use Playwright for full JS rendering
        soup = self.http.get_rendered_soup(
            url,
            params=params,
            wait_selector="div.result-item, a[class*='result'], [data-testid='result']",
            wait_ms=4000,
        )

        # Check if BBB returned a "no results" page (search might be blocked)
        title_el = soup.select_one("title")
        title_text = title_el.get_text() if title_el else ""
        if "No Results" in title_text or "No results" in title_text:
            logger.warning(
                "[BBB] Search returned no results — BBB may be blocking the request. "
                "BBB may require residential proxies for reliable scraping. "
                "Set PROXY_URL in .env to bypass."
            )
            return []

        # Try to extract from embedded JSON data first (BBB often uses React)
        leads = self._extract_from_json(soup)
        if leads:
            return leads

        # Fall back to HTML parsing
        results = soup.select("div.result-item, li.result-item, div[data-testid='result']")

        if not results:
            results = soup.select("a[class*='result'], div[class*='search-result']")

        if not results:
            # Try broader selectors for BBB's React-rendered content
            results = soup.select(
                "[class*='result-list'] > div, "
                "[class*='BusinessCard'], "
                "[class*='listing-item']"
            )

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

    def _extract_from_json(self, soup: BeautifulSoup) -> list[dict]:
        """Try to extract from embedded JSON (BBB uses React/Next.js)."""
        leads = []

        # Look for __NEXT_DATA__ or inline JSON
        scripts = soup.select("script")
        for script in scripts:
            text = script.string or ""
            if "__NEXT_DATA__" in text or '"searchResults"' in text or '"businesses"' in text:
                try:
                    match = re.search(r'__NEXT_DATA__\s*=\s*({.+?})\s*;\s*</script>', text, re.DOTALL)
                    if not match:
                        match = re.search(r'({.+?"searchResults".+?})', text, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        leads = self._walk_json_for_businesses(data)
                        if leads:
                            return leads
                except (json.JSONDecodeError, AttributeError):
                    continue

        # Also try JSON-LD
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        lead = self._parse_jsonld_business(item)
                        if lead:
                            leads.append(lead)
                elif isinstance(data, dict):
                    lead = self._parse_jsonld_business(data)
                    if lead:
                        leads.append(lead)
            except (json.JSONDecodeError, AttributeError):
                continue

        return leads

    def _walk_json_for_businesses(self, data, depth: int = 0) -> list[dict]:
        """Recursively walk JSON to find business data."""
        if depth > 8:
            return []
        results = []
        if isinstance(data, dict):
            if data.get("businessName") or (data.get("name") and data.get("phone")):
                lead = self._parse_json_business(data)
                if lead:
                    results.append(lead)
            else:
                for v in data.values():
                    results.extend(self._walk_json_for_businesses(v, depth + 1))
        elif isinstance(data, list):
            for item in data[:50]:
                results.extend(self._walk_json_for_businesses(item, depth + 1))
        return results

    def _parse_json_business(self, data: dict) -> dict | None:
        """Parse a business from BBB's embedded JSON."""
        name = data.get("businessName", data.get("name", ""))
        if not name or len(name) < 2:
            return None

        address = ""
        city = ""
        state = ""
        zip_code = ""

        addr = data.get("address", data.get("location", {}))
        if isinstance(addr, dict):
            address = addr.get("streetAddress", addr.get("address", ""))
            city = addr.get("city", addr.get("addressLocality", ""))
            state = addr.get("state", addr.get("addressRegion", ""))
            zip_code = addr.get("postalCode", addr.get("zipCode", ""))

        return {
            "business_name": name,
            "phone": data.get("phone", data.get("telephone")),
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "website": data.get("website", data.get("websiteUrl")),
            "category": data.get("category", data.get("primaryCategory", "")),
            "bbb_rating": data.get("rating", data.get("bbbRating")),
            "bbb_accredited": data.get("isAccredited", data.get("accredited", False)),
            "source_url": data.get("url", data.get("profileUrl", "")),
        }

    def _parse_jsonld_business(self, item: dict) -> dict | None:
        """Parse JSON-LD structured business data."""
        if not isinstance(item, dict):
            return None
        item_type = item.get("@type", "")
        if "Business" not in item_type and "Organization" not in item_type:
            return None

        name = item.get("name")
        if not name:
            return None

        addr = item.get("address", {})
        return {
            "business_name": name,
            "phone": item.get("telephone"),
            "address": addr.get("streetAddress", ""),
            "city": addr.get("addressLocality", ""),
            "state": addr.get("addressRegion", ""),
            "zip_code": addr.get("postalCode", ""),
            "website": item.get("url"),
            "source_url": item.get("url", ""),
        }

    def _parse_listing(self, card) -> dict | None:
        """Parse a single BBB business listing from HTML."""
        # Business name
        name_el = card.select_one("h3 a, .result-name a, a[class*='business-name'], [class*='Name'] a")
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
        if not phone:
            # Search for phone pattern in card text
            card_text = card.get_text()
            phone_match = re.search(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', card_text)
            if phone_match:
                phone = phone_match.group(0)

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
