"""Phone number discovery enrichment — finds phone numbers when missing."""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# US phone patterns
PHONE_RE = re.compile(
    r'(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.\-]?(\d{3})[\s.\-]?(\d{4})'
)


class PhoneDiscoveryEnricher(BaseEnricher):
    """Find phone numbers for businesses that don't have one."""

    MODULE_NAME = "phone_discovery"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        if lead.phone:
            return {}

        name = lead.businessName or ""
        city = lead.city or ""
        state = lead.state or ""

        if not name:
            return {}

        # Strategy 1: Google search
        phone = self._google_search(name, city, state)

        # Strategy 2: Website (tel: links, schema.org)
        if not phone and lead.website:
            phone = self._from_website(lead.website)

        if phone:
            logger.debug(f"[PhoneDiscovery] Found phone for {name}: {phone}")
            return {"phone": phone}

        return {}

    def _google_search(self, name: str, city: str, state: str) -> str | None:
        """Search Google for the business phone number."""
        query = f"{name} {city} {state} phone number"
        url = f"https://www.google.com/search?q={quote_plus(query)}"

        try:
            soup = self.http.get_soup(url)
        except Exception as e:
            logger.debug(f"[PhoneDiscovery] Google search failed: {e}")
            return None

        text = soup.get_text(separator=" ")

        # Extract all phone numbers
        matches = PHONE_RE.findall(text)
        for area, prefix, line in matches:
            phone = f"({area}) {prefix}-{line}"
            # Skip 800/888 toll-free unless it's the only option
            if area not in ("800", "888", "877", "866", "855"):
                return phone

        # Fall back to toll-free if that's all we have
        if matches:
            area, prefix, line = matches[0]
            return f"({area}) {prefix}-{line}"

        return None

    def _from_website(self, website: str) -> str | None:
        """Extract phone from the business website."""
        try:
            soup = self.http.get_soup(website)
        except Exception:
            return None

        # Check tel: links first (most reliable)
        for a in soup.select('a[href^="tel:"]'):
            href = a.get("href", "")
            digits = re.sub(r"[^\d]", "", href.replace("tel:", ""))
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

        # Check JSON-LD
        import json
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string)
                phone = self._phone_from_jsonld(data)
                if phone:
                    return phone
            except (json.JSONDecodeError, TypeError):
                continue

        # Check page text for phone numbers
        text = soup.get_text(separator=" ")
        matches = PHONE_RE.findall(text)
        if matches:
            area, prefix, line = matches[0]
            return f"({area}) {prefix}-{line}"

        return None

    def _phone_from_jsonld(self, data) -> str | None:
        """Extract phone from JSON-LD structured data."""
        if isinstance(data, dict):
            for key in ("telephone", "phone", "contactPoint"):
                val = data.get(key)
                if isinstance(val, str):
                    digits = re.sub(r"[^\d]", "", val)
                    if len(digits) == 11 and digits.startswith("1"):
                        digits = digits[1:]
                    if len(digits) == 10:
                        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                elif isinstance(val, dict):
                    result = self._phone_from_jsonld(val)
                    if result:
                        return result
                elif isinstance(val, list):
                    for item in val:
                        result = self._phone_from_jsonld(item)
                        if result:
                            return result
        return None

    def close(self):
        self.http.close()
