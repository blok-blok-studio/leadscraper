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
        """Scrape a single Yelp search results page using Playwright."""
        url = f"{self.BASE_URL}/search"
        params = {
            "find_desc": category,
            "find_loc": location,
            "start": start,
        }

        # Use Playwright for full JS rendering
        soup = self.http.get_rendered_soup(
            url,
            params=params,
            wait_selector='[class*="searchResult"], [data-testid*="serp"]',
            wait_ms=4000,
        )

        # Check if Yelp blocked us (returns near-empty page)
        page_size = len(str(soup))
        if page_size < 5000:
            logger.warning(
                "[Yelp] Page appears blocked (only %d bytes). "
                "Yelp requires residential proxies for reliable scraping. "
                "Set PROXY_URL in .env to bypass.", page_size
            )
            return []

        # Try to extract from JSON-LD structured data first
        leads = self._extract_from_jsonld(soup)
        if leads:
            return leads

        # Try to extract from embedded __NEXT_DATA__ or Apollo state
        leads = self._extract_from_next_data(soup)
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

    def _extract_from_next_data(self, soup: BeautifulSoup) -> list[dict]:
        """Try to extract from __NEXT_DATA__ or inline JSON blobs Yelp embeds."""
        leads = []
        scripts = soup.select("script")
        for script in scripts:
            text = script.string or ""
            # Look for JSON blobs with business data
            if "searchPageProps" in text or '"bizId"' in text or '"searchResultBusiness"' in text:
                try:
                    # Try to find a JSON blob
                    for pattern in [
                        r'__NEXT_DATA__\s*=\s*({.+?})\s*;',
                        r'window\.__INITIAL_STATE__\s*=\s*({.+?})\s*;',
                    ]:
                        match = re.search(pattern, text, re.DOTALL)
                        if match:
                            data = json.loads(match.group(1))
                            extracted = self._walk_json_for_businesses(data)
                            if extracted:
                                leads.extend(extracted)
                                return leads
                except (json.JSONDecodeError, AttributeError):
                    continue
        return leads

    def _walk_json_for_businesses(self, data, depth: int = 0) -> list[dict]:
        """Recursively walk a JSON structure to find business listings."""
        if depth > 10:
            return []
        results = []
        if isinstance(data, dict):
            # Check if this dict looks like a business
            if data.get("name") and (data.get("phone") or data.get("address")):
                lead = self._parse_json_business(data)
                if lead:
                    results.append(lead)
            else:
                for v in data.values():
                    results.extend(self._walk_json_for_businesses(v, depth + 1))
        elif isinstance(data, list):
            for item in data[:50]:  # Limit to prevent infinite recursion
                results.extend(self._walk_json_for_businesses(item, depth + 1))
        return results

    def _parse_json_business(self, data: dict) -> dict | None:
        """Parse a business dict from embedded JSON."""
        name = data.get("name", "")
        if not name or len(name) < 2:
            return None

        address = ""
        city = ""
        state = ""
        zip_code = ""

        addr = data.get("address", data.get("location", {}))
        if isinstance(addr, dict):
            address = addr.get("streetAddress", addr.get("address1", ""))
            city = addr.get("addressLocality", addr.get("city", ""))
            state = addr.get("addressRegion", addr.get("state", ""))
            zip_code = addr.get("postalCode", addr.get("zipCode", ""))
        elif isinstance(addr, str):
            address = addr

        rating = data.get("rating", data.get("averageRating"))
        review_count = data.get("reviewCount", data.get("numReviews"))

        return {
            "business_name": name,
            "phone": data.get("phone", data.get("displayPhone")),
            "address": address,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "website": data.get("website", data.get("url")),
            "yelp_rating": float(rating) if rating else None,
            "yelp_review_count": int(review_count) if review_count else None,
            "source_url": data.get("businessUrl", data.get("url", "")),
        }

    def _extract_from_html(self, soup: BeautifulSoup) -> list[dict]:
        """Fallback HTML parsing for Yelp results."""
        leads = []

        # Yelp uses various container class patterns
        containers = soup.select(
            '[class*="container"] [class*="searchResult"], '
            'li[class*="result"], '
            'div[data-testid*="serp-ia-card"], '
            '[class*="arrange-unit"] [class*="businessName"], '
            'div[class*="list__"] > div'
        )

        # Also try finding by common link patterns
        if not containers:
            biz_links = soup.select('a[href*="/biz/"]')
            seen_names = set()
            for link in biz_links:
                parent = link.find_parent("div")
                if parent and parent not in containers:
                    name = link.get_text(strip=True)
                    if name and name not in seen_names and not name.startswith("http"):
                        seen_names.add(name)
                        containers.append(parent)

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
            'a[class*="businessName"], h3 a, [class*="heading"] a, '
            'a[href*="/biz/"]'
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        # Strip leading numbers like "1. " or "2. "
        name = re.sub(r"^\d+\.\s*", "", name)
        if not name or len(name) < 2:
            return None

        # Phone
        phone = None
        phone_el = card.select_one('[class*="phone"], a[href^="tel:"]')
        if phone_el:
            phone = phone_el.get_text(strip=True)
        if not phone:
            # Look for phone pattern in text
            card_text = card.get_text()
            phone_match = re.search(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', card_text)
            if phone_match:
                phone = phone_match.group(0)

        # Address
        address = ""
        city = ""
        state = ""
        zip_code = ""
        addr_el = card.select_one('[class*="address"], address, [class*="secondaryAttributes"]')
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
        rating_el = card.select_one('[class*="rating"], [aria-label*="rating"], [aria-label*="star"]')
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
