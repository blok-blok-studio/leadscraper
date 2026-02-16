"""Social media link discovery enrichment module."""

from __future__ import annotations

import logging
import re

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

SOCIAL_PATTERNS = {
    "facebook_url": [
        r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9._-]+/?',
        r'https?://(?:www\.)?fb\.com/[a-zA-Z0-9._-]+/?',
    ],
    "instagram_url": [
        r'https?://(?:www\.)?instagram\.com/[a-zA-Z0-9._-]+/?',
    ],
    "twitter_url": [
        r'https?://(?:www\.)?(?:twitter|x)\.com/[a-zA-Z0-9_]+/?',
    ],
    "linkedin_url": [
        r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[a-zA-Z0-9._-]+/?',
    ],
    "youtube_url": [
        r'https?://(?:www\.)?youtube\.com/(?:channel|c|user|@)[a-zA-Z0-9._-]+/?',
    ],
    "tiktok_url": [
        r'https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9._-]+/?',
    ],
}

# Filter out generic/login pages
EXCLUDED_PATHS = {
    "facebook_url": ["sharer", "login", "dialog", "share.php", "groups"],
    "instagram_url": ["accounts", "explore"],
    "twitter_url": ["intent", "share", "home"],
    "linkedin_url": ["login", "signup", "shareArticle"],
    "youtube_url": ["watch", "results", "feed"],
    "tiktok_url": ["login"],
}


class SocialMediaEnricher(BaseEnricher):
    """Find social media profiles from a business website."""

    MODULE_NAME = "social_media"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        if not lead.website:
            return {}

        try:
            response = self.http.get(lead.website)
            html = response.text
        except Exception as e:
            logger.debug(f"[Social] Could not fetch {lead.website}: {e}")
            return {}

        result = {}

        for field, patterns in SOCIAL_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if not self._is_excluded(field, match):
                        result[field] = match.rstrip("/")
                        break
                if field in result:
                    break

        if result:
            logger.debug(
                f"[Social] Found {len(result)} social links for {lead.businessName}"
            )

        return result

    def _is_excluded(self, field: str, url: str) -> bool:
        """Check if the URL is a generic/login page, not a business profile."""
        excluded = EXCLUDED_PATHS.get(field, [])
        url_lower = url.lower()
        return any(excl in url_lower for excl in excluded)

    def close(self):
        self.http.close()
