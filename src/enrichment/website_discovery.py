"""Website discovery enrichment — finds the business website via Google search."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# Domains to exclude (these are directories, not business websites)
EXCLUDED_DOMAINS = {
    "yelp.com", "yellowpages.com", "bbb.org", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "tiktok.com", "mapquest.com", "superpages.com",
    "whitepages.com", "manta.com", "angieslist.com", "homeadvisor.com",
    "thumbtack.com", "nextdoor.com", "google.com", "bing.com",
    "apple.com", "amazon.com", "wikipedia.org", "tripadvisor.com",
    "indeed.com", "glassdoor.com", "foursquare.com", "porch.com",
    "houzz.com", "bark.com", "expertise.com", "citysearch.com",
    "chamberofcommerce.com", "dandb.com", "merchantcircle.com",
    "buildzoom.com", "networx.com", "angi.com", "pinterest.com",
    "reddit.com",
}


class WebsiteDiscoveryEnricher(BaseEnricher):
    """Find a business website via Google search when one isn't known."""

    MODULE_NAME = "website_discovery"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        # Skip if website already known
        if lead.website:
            return {}

        name = lead.businessName or ""
        city = lead.city or ""
        state = lead.state or ""

        if not name:
            return {}

        # Strategy 1: Google search for the business
        website = self._google_search(name, city, state)

        if not website:
            # Strategy 2: Try with phone number in query (more specific)
            phone = lead.phone or ""
            if phone:
                website = self._google_search(f"{name} {phone}", city, state)

        if not website:
            # Strategy 3: Try direct URL guessing
            website = self._guess_url(name)

        if website:
            logger.debug(f"[WebDiscovery] Found website for {name}: {website}")
            return {
                "website": website,
                "has_website": True,
            }

        return {}

    def _google_search(self, query: str, city: str, state: str) -> str | None:
        """Search Google and extract the most likely business website."""
        search_query = f"{query} {city} {state}".strip()
        url = f"https://www.google.com/search?q={quote_plus(search_query)}&num=10"

        try:
            soup = self.http.get_soup(url)
        except Exception as e:
            logger.debug(f"[WebDiscovery] Google search failed: {e}")
            return None

        # Extract URLs from search results
        candidates = []

        # Method 1: Parse <a> tags with actual URLs
        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "")
            # Google wraps results in /url?q=REAL_URL&...
            if href.startswith("/url?q="):
                real_url = href.split("/url?q=")[1].split("&")[0]
                if real_url.startswith("http"):
                    candidates.append(real_url)
            elif href.startswith("http") and "google.com" not in href:
                candidates.append(href)

        # Method 2: Look for cite elements (Google shows URL in green text)
        for cite in soup.select("cite"):
            text = cite.get_text().strip()
            if text.startswith("http"):
                candidates.append(text)
            elif "." in text and "/" not in text[:20]:
                candidates.append(f"https://{text.split(' ')[0]}")

        # Method 3: Regex for URLs in page text
        url_pattern = re.compile(
            r'https?://[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}(?:/[^\s"<>]*)?'
        )
        page_text = soup.get_text()
        for match in url_pattern.findall(page_text):
            candidates.append(match)

        # Filter and rank candidates
        for candidate in candidates:
            parsed = urlparse(candidate)
            domain = parsed.netloc.lower().replace("www.", "")

            # Skip excluded domains
            if any(excluded in domain for excluded in EXCLUDED_DOMAINS):
                continue

            # Skip non-http schemes
            if parsed.scheme not in ("http", "https"):
                continue

            # Prefer actual business domains (not deep paths on directories)
            # Return the first valid candidate
            clean_url = f"{parsed.scheme}://{parsed.netloc}"
            return clean_url

        return None

    def _guess_url(self, business_name: str) -> str | None:
        """Try common domain patterns for the business name."""
        # Clean name: "Joe's Plumbing LLC" -> "joesplumbing"
        clean = re.sub(r"[^a-z0-9]", "", business_name.lower())
        clean = re.sub(r"(llc|inc|corp|co|ltd|company)$", "", clean)

        if len(clean) < 3:
            return None

        # Try common TLDs
        for tld in [".com", ".net"]:
            url = f"https://www.{clean}{tld}"
            try:
                response = self.http.get(url)
                if response.status_code == 200 and len(response.text) > 1000:
                    return url
            except Exception:
                continue

        return None

    def close(self):
        self.http.close()
