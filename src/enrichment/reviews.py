"""Reviews and ratings enrichment module."""

from __future__ import annotations

import logging
import re
import json
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)


class ReviewsEnricher(BaseEnricher):
    """Enrich leads with Google and Yelp review data."""

    MODULE_NAME = "reviews_ratings"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        result = {}

        # Try Google Business Profile
        google_data = self._search_google_business(lead)
        if google_data:
            result.update(google_data)

        # Try Yelp search
        if not lead.yelpRating:
            yelp_data = self._search_yelp(lead)
            if yelp_data:
                result.update(yelp_data)

        return result

    def _search_google_business(self, lead) -> dict:
        """Search for the business on Google to find its Business Profile data."""
        query = f"{lead.businessName} {lead.city} {lead.state}"
        search_url = f"https://www.google.com/search?q={quote_plus(query)}"

        try:
            soup = self.http.get_soup(search_url)
        except Exception as e:
            logger.debug(f"[Reviews] Google search failed for {lead.businessName}: {e}")
            return {}

        result = {}

        # Look for rating in the knowledge panel / local pack
        # Google shows ratings like "4.5 (123 reviews)"
        page_text = soup.get_text()

        rating_pattern = r'(\d\.\d)\s*(?:\(|·)\s*(\d[\d,]*)\s*(?:reviews?|ratings?)'
        match = re.search(rating_pattern, page_text, re.IGNORECASE)
        if match:
            try:
                result["google_rating"] = float(match.group(1))
                result["google_review_count"] = int(match.group(2).replace(",", ""))
            except (ValueError, TypeError):
                pass

        # Check for Google Business Profile
        if soup.select_one('[data-attrid*="kc:"], .knowledge-panel, .kp-wholepage'):
            result["has_google_business_profile"] = True
        elif "business.site" in page_text or "google.com/maps" in page_text:
            result["has_google_business_profile"] = True

        return result

    def _search_yelp(self, lead) -> dict:
        """Search for the business on Yelp."""
        query = quote_plus(lead.businessName)
        location = quote_plus(f"{lead.city}, {lead.state}")
        url = f"https://www.yelp.com/search?find_desc={query}&find_loc={location}"

        try:
            soup = self.http.get_soup(url)
        except Exception as e:
            logger.debug(f"[Reviews] Yelp search failed for {lead.businessName}: {e}")
            return {}

        result = {}

        # Try JSON-LD data first
        scripts = soup.select('script[type="application/ld+json"]')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    items = data.get("itemListElement", [])
                    for item in items:
                        biz = item.get("item", {})
                        biz_name = biz.get("name", "")
                        if self._names_match(biz_name, lead.businessName):
                            rating_data = biz.get("aggregateRating", {})
                            if rating_data:
                                result["yelp_rating"] = float(
                                    rating_data.get("ratingValue", 0)
                                ) or None
                                result["yelp_review_count"] = int(
                                    rating_data.get("reviewCount", 0)
                                ) or None
                            return result
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        return result

    def _names_match(self, name1: str, name2: str) -> bool:
        """Fuzzy match two business names."""
        n1 = re.sub(r"[^a-z0-9]", "", name1.lower())
        n2 = re.sub(r"[^a-z0-9]", "", name2.lower())
        return n1 == n2 or n1 in n2 or n2 in n1

    def close(self):
        self.http.close()
