"""Contact and decision maker enrichment module."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# Common "about" or "team" page paths
ABOUT_PATHS = [
    "/about", "/about-us", "/about-me", "/our-team", "/team",
    "/staff", "/leadership", "/management", "/contact",
    "/contact-us", "/our-story",
]

# Title patterns for decision makers
DECISION_MAKER_TITLES = [
    r"owner", r"founder", r"co-founder", r"ceo", r"president",
    r"director", r"manager", r"principal", r"partner",
    r"proprietor", r"chief",
]

# Email patterns in page text
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)


class ContactEnricher(BaseEnricher):
    """Find owner/decision maker contact info from business websites."""

    MODULE_NAME = "contact_enrichment"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        if not lead.website:
            return {}

        result = {}

        # First check the homepage for contact info
        try:
            homepage_soup = self.http.get_soup(lead.website)
            result.update(self._extract_emails(homepage_soup, lead))
            result.update(self._extract_owner_info(homepage_soup))
        except Exception as e:
            logger.debug(f"[Contact] Could not fetch homepage {lead.website}: {e}")

        # If we didn't find an owner, check about/team pages
        if not result.get("owner_name"):
            for path in ABOUT_PATHS:
                try:
                    url = lead.website.rstrip("/") + path
                    soup = self.http.get_soup(url)
                    owner_info = self._extract_owner_info(soup)
                    if owner_info.get("owner_name"):
                        result.update(owner_info)
                        # Also check for emails on this page
                        result.update(self._extract_emails(soup, lead))
                        break
                except Exception:
                    continue

        # Try to find a LinkedIn profile for the owner
        if result.get("owner_name") and not result.get("owner_linkedin"):
            linkedin = self._find_owner_linkedin(homepage_soup if 'homepage_soup' in dir() else None)
            if linkedin:
                result["owner_linkedin"] = linkedin

        return result

    def _extract_emails(self, soup: BeautifulSoup, lead) -> dict:
        """Extract email addresses from page content."""
        result = {}
        page_text = soup.get_text()

        emails = EMAIL_PATTERN.findall(page_text)
        # Also check mailto: links
        mailto_links = soup.select('a[href^="mailto:"]')
        for link in mailto_links:
            href = link.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email and email not in emails:
                emails.append(email)

        # Filter out generic/noreply emails
        filtered = [
            e for e in emails
            if not any(x in e.lower() for x in [
                "noreply", "no-reply", "donotreply", "example.com",
                "sentry.io", "wixpress", "wordpress", "squarespace",
            ])
        ]

        if filtered:
            # Prefer info@, contact@, or owner-looking emails
            business_email = None
            owner_email = None
            for email in filtered:
                local = email.split("@")[0].lower()
                if local in ("info", "contact", "hello", "support"):
                    business_email = email
                elif not any(x in local for x in ["info", "contact", "support", "hello", "admin", "sales"]):
                    owner_email = email

            if not lead.email and business_email:
                result["email"] = business_email
            if owner_email:
                result["owner_email"] = owner_email
            elif not result.get("owner_email") and filtered:
                result["owner_email"] = filtered[0]

        return result

    def _extract_owner_info(self, soup: BeautifulSoup) -> dict:
        """Try to extract owner/decision maker name and title from a page."""
        result = {}
        page_text = soup.get_text(separator=" ")

        # Look for title patterns near names
        title_pattern = "|".join(DECISION_MAKER_TITLES)
        patterns = [
            # "John Smith, Owner"
            rf'([A-Z][a-z]+ [A-Z][a-z]+)\s*[,\-–—]\s*({title_pattern})',
            # "Owner: John Smith"
            rf'({title_pattern})\s*[:\-–—]\s*([A-Z][a-z]+ [A-Z][a-z]+)',
            # "Meet our Owner John Smith"
            rf'(?:meet\s+(?:our\s+)?|about\s+)({title_pattern})\s+([A-Z][a-z]+ [A-Z][a-z]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Determine which group is name vs title
                    g1, g2 = groups
                    if re.match(r'[A-Z][a-z]+ [A-Z][a-z]+', g1):
                        result["owner_name"] = g1.strip()
                        result["owner_title"] = g2.strip().title()
                    else:
                        result["owner_name"] = g2.strip()
                        result["owner_title"] = g1.strip().title()
                break

        # Check schema.org/structured data
        if not result.get("owner_name"):
            schema_scripts = soup.select('script[type="application/ld+json"]')
            import json
            for script in schema_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        founder = data.get("founder") or data.get("employee")
                        if isinstance(founder, dict):
                            name = founder.get("name")
                            if name:
                                result["owner_name"] = name
                                result["owner_title"] = founder.get("jobTitle", "Owner")
                                break
                        elif isinstance(founder, list) and founder:
                            first = founder[0]
                            if isinstance(first, dict) and first.get("name"):
                                result["owner_name"] = first["name"]
                                result["owner_title"] = first.get("jobTitle", "Owner")
                                break
                except (json.JSONDecodeError, AttributeError, TypeError):
                    continue

        return result

    def _find_owner_linkedin(self, soup: BeautifulSoup) -> str | None:
        """Try to find a LinkedIn profile URL for the owner."""
        if not soup:
            return None
        linkedin_links = soup.select('a[href*="linkedin.com/in/"]')
        for link in linkedin_links:
            href = link.get("href", "")
            if "/in/" in href and "company" not in href:
                return href.rstrip("/")
        return None

    def close(self):
        self.http.close()
