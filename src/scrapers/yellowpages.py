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
        """Scrape a single results page using Playwright for JS rendering."""
        url = f"{self.BASE_URL}/search"
        params = {
            "search_terms": category,
            "geo_location_terms": location,
            "page": page,
        }

        # Use Playwright browser rendering to bypass anti-bot protection
        soup = self.http.get_rendered_soup(
            url,
            params=params,
            wait_selector="li.business-card, section.info",
            wait_ms=4000,
        )

        # Primary selector: each listing is an <li class="business-card">
        results = soup.select("li.business-card")

        if not results:
            # Fallback to older selectors
            results = soup.select("div.result, div.v-card, div.srp-listing")

        # Filter out sponsored-only cards that lack real data
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
        # Business name — <h2 class="title business-name"> (may or may not contain <a>)
        name_el = card.select_one(
            "h2.business-name a, h2.title a, "
            "h2.business-name, h2.title, "
            "span.business-name, a.business-name, "
            "h2.n a, .info h2 a, .info h2"
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        # Strip leading numbers like "1." or "2."
        name = re.sub(r"^\d+\.\s*", "", name).strip()
        if not name:
            return None

        # Phone — look for tel: links or phone pattern in text
        phone = None
        phone_el = card.select_one("a[href^='tel:'], div.phones, .phone")
        if phone_el:
            if phone_el.get("href", "").startswith("tel:"):
                phone = phone_el["href"].replace("tel:", "").strip()
            else:
                phone = phone_el.get_text(strip=True)
        if not phone:
            # Regex fallback: find phone number pattern in card text
            card_text = card.get_text()
            phone_match = re.search(r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', card_text)
            if phone_match:
                phone = phone_match.group(0)

        # Address — <article class="address-indicators"> or <article class="address">
        address = ""
        city = ""
        state = ""
        zip_code = ""

        addr_el = card.select_one(
            "article.address-indicators, article.address, "
            "div.street-address, .adr"
        )
        if addr_el:
            addr_text = addr_el.get_text(separator=", ", strip=True)
            # Try pattern: "Street, City, ST ZIP" or "Street City, ST"
            match = re.match(
                r"(.+?),\s*(.+?),\s*([A-Z]{2})\s*(\d{5})?",
                addr_text
            )
            if match:
                address = match.group(1).strip()
                city = match.group(2).strip()
                state = match.group(3).strip()
                zip_code = (match.group(4) or "").strip()
            else:
                # Try "Street City, ST" (no comma between street and city)
                match2 = re.match(r"(.+?),?\s+([A-Z]{2})\s*(\d{5})?$", addr_text)
                if match2:
                    address = match2.group(1).strip()
                    state = match2.group(2).strip()
                    zip_code = (match2.group(3) or "").strip()

        # Website — <a class="website listing-cta action">
        website = None
        website_el = card.select_one(
            "a.website, a.track-visit-website, "
            "a[class*='website']"
        )
        if website_el:
            href = website_el.get("href", "")
            if href and not href.startswith("/") and "yellowpages.com" not in href:
                website = href

        # Category — look for category links or text
        category_text = ""
        cat_els = card.select("a[href*='/category/'], div.categories a, p.indicators a")
        if cat_els:
            category_text = ", ".join(
                el.get_text(strip=True) for el in cat_els
                if el.get_text(strip=True) and "Yellow Pages" not in el.get_text()
            )

        # Source URL — link to the business detail page
        source_url = ""
        link_el = card.select_one("h2.title a, h2.business-name a, a.business-name")
        if link_el and link_el.get("href"):
            href = link_el["href"]
            source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
        if not source_url:
            # Try any link that goes to a YP detail page
            detail_link = card.select_one("a[href*='/mip/']")
            if detail_link and detail_link.get("href"):
                href = detail_link["href"]
                source_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Years in business
        year_established = None
        years_el = card.select_one(".years-in-business .count, .yib")
        if years_el:
            try:
                years_text = years_el.get_text(strip=True)
                years = int(re.sub(r"\D", "", years_text))
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
