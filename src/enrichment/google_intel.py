"""Google Intelligence — single comprehensive Google search replaces 7-9 scattered searches.

Instead of each module (email_discovery, phone_discovery, contact_enrichment, reviews)
independently hitting Google 1-3 times each, this module does ONE search query
and extracts everything: website, phone, email, owner name, rating, and GBP status.

Then downstream modules see the data is already populated and skip their own Google searches.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urlparse

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# Email regex
EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

# Phone regex (US)
PHONE_RE = re.compile(
    r'(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.\-]?(\d{3})[\s.\-]?(\d{4})'
)

# Domains to exclude as business websites
EXCLUDED_DOMAINS = {
    "yelp.com", "yellowpages.com", "bbb.org", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "tiktok.com", "mapquest.com", "superpages.com",
    "whitepages.com", "manta.com", "angieslist.com", "homeadvisor.com",
    "thumbtack.com", "nextdoor.com", "google.com", "bing.com",
    "apple.com", "amazon.com", "wikipedia.org", "tripadvisor.com",
    "indeed.com", "glassdoor.com", "foursquare.com", "porch.com",
    "houzz.com", "bark.com", "expertise.com", "citysearch.com",
    "pinterest.com", "reddit.com",
}

# Junk email domains
JUNK_EMAIL_DOMAINS = {
    "example.com", "domain.com", "email.com", "test.com",
    "sentry.io", "wixpress.com", "wordpress.com",
    "squarespace.com", "w3.org", "schema.org", "googleapis.com",
    "google.com", "facebook.com", "twitter.com", "gstatic.com",
}

# Generic email prefixes
GENERIC_PREFIXES = {
    "info", "contact", "hello", "support", "admin", "sales",
    "billing", "office", "help", "service", "team", "noreply",
    "no-reply", "webmaster",
}

# Owner title patterns
DECISION_MAKER_TITLES = [
    "owner", "founder", "co-founder", "cofounder",
    "ceo", "president", "managing director",
    "principal", "proprietor", "partner",
]


class GoogleIntelEnricher(BaseEnricher):
    """Single comprehensive Google search to extract multiple data points.

    Replaces 7-9 separate Google searches across modules with 1-2 queries.
    Extracts: website, phone, email, owner name/title, rating, review count, GBP.
    """

    MODULE_NAME = "google_intel"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        result = {}
        name = lead.businessName or ""
        city = lead.city or ""
        state = lead.state or ""

        if not name:
            return {}

        # ── Query 1: Comprehensive business search ──
        query = f'"{name}" {city} {state}'
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=10"

        try:
            soup = self.http.get_soup(url, use_cache=False)
            text = soup.get_text(separator=" ")
        except Exception as e:
            logger.debug(f"[GoogleIntel] Search failed for {name}: {e}")
            return {}

        # Extract website (if not already known)
        if not lead.website:
            website = self._extract_website(soup)
            if website:
                result["website"] = website
                result["has_website"] = True

        # Extract phone (if not already known)
        if not lead.phone:
            phone = self._extract_phone(text)
            if phone:
                result["phone"] = phone

        # Extract email
        email = self._extract_email(text, lead.website)
        if email:
            current_email = lead.email or ""
            current_local = current_email.split("@")[0].lower() if current_email else ""
            new_local = email.split("@")[0].lower()

            # Set if no email, or upgrade from generic to personal
            if not current_email:
                result["email"] = email
            elif current_local in GENERIC_PREFIXES and new_local not in GENERIC_PREFIXES:
                result["email"] = email

        # Extract owner name + title
        if not getattr(lead, "ownerName", None):
            owner_data = self._extract_owner(text)
            if owner_data:
                result.update(owner_data)

        # Extract Google rating and review count
        if not getattr(lead, "googleRating", None):
            rating_data = self._extract_rating(text)
            if rating_data:
                result.update(rating_data)

        # Check for Google Business Profile
        page_text = soup.get_text()
        if soup.select_one('[data-attrid*="kc:"], .knowledge-panel, .kp-wholepage'):
            result["has_google_business_profile"] = True
        elif "business.site" in page_text or "google.com/maps" in page_text:
            result["has_google_business_profile"] = True

        # ── Query 2 (optional): LinkedIn search only if owner found ──
        owner_name = result.get("owner_name") or getattr(lead, "ownerName", None)
        existing_linkedin = getattr(lead, "ownerLinkedin", None)
        if owner_name and not existing_linkedin:
            linkedin = self._find_linkedin(name, owner_name)
            if linkedin:
                result["owner_linkedin"] = linkedin

        if result:
            logger.debug(
                f"[GoogleIntel] Found {len(result)} fields for {name}: "
                f"{list(result.keys())}"
            )

        return result

    def _extract_website(self, soup) -> str | None:
        """Extract business website from Google search results."""
        candidates = []

        # Method 1: Parse <a> tags with actual URLs
        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "")
            if href.startswith("/url?q="):
                real_url = href.split("/url?q=")[1].split("&")[0]
                if real_url.startswith("http"):
                    candidates.append(real_url)
            elif href.startswith("http") and "google.com" not in href:
                candidates.append(href)

        # Method 2: cite elements
        for cite in soup.select("cite"):
            text = cite.get_text().strip()
            if text.startswith("http"):
                candidates.append(text)
            elif "." in text and "/" not in text[:20]:
                candidates.append(f"https://{text.split(' ')[0]}")

        # Filter and return first valid business website
        for candidate in candidates:
            parsed = urlparse(candidate)
            domain = parsed.netloc.lower().replace("www.", "")
            if any(excluded in domain for excluded in EXCLUDED_DOMAINS):
                continue
            if parsed.scheme not in ("http", "https"):
                continue
            return f"{parsed.scheme}://{parsed.netloc}"

        return None

    def _extract_phone(self, text: str) -> str | None:
        """Extract phone number from search results text."""
        matches = PHONE_RE.findall(text)
        for area, prefix, line in matches:
            # Skip toll-free unless it's the only option
            if area not in ("800", "888", "877", "866", "855"):
                return f"({area}) {prefix}-{line}"

        # Fall back to toll-free
        if matches:
            area, prefix, line = matches[0]
            return f"({area}) {prefix}-{line}"

        return None

    def _extract_email(self, text: str, website: str | None) -> str | None:
        """Extract best email from search results text."""
        emails = EMAIL_RE.findall(text)

        # Get business domain for preference
        biz_domain = ""
        if website:
            biz_domain = urlparse(website).netloc.replace("www.", "")

        personal = []
        generic = []

        for email in emails:
            email = email.lower()
            domain = email.split("@")[1] if "@" in email else ""
            local = email.split("@")[0]

            if domain in JUNK_EMAIL_DOMAINS:
                continue
            if len(email) > 50:
                continue

            # Prefer emails from business domain
            if biz_domain and biz_domain in domain:
                if local not in GENERIC_PREFIXES:
                    personal.append(email)
                else:
                    generic.append(email)
            elif local not in GENERIC_PREFIXES:
                personal.append(email)

        # Return best email
        if personal:
            return personal[0]
        if generic:
            return generic[0]
        return None

    def _extract_owner(self, text: str) -> dict | None:
        """Extract owner/founder name from search results text."""
        title_pattern = "|".join(re.escape(t) for t in DECISION_MAKER_TITLES)
        patterns = [
            # "John Smith, Owner"
            rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[,\-–—|/]\s*({title_pattern})',
            # "Owner: John Smith"
            rf'({title_pattern})\s*[:\-–—|/]\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "owned by John Smith"
            rf'(?:owned|founded|started)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    g1, g2 = groups
                    # Figure out which is name vs title
                    if re.match(r'[A-Z][a-z]+', g1) and not any(
                        t in g1.lower() for t in DECISION_MAKER_TITLES
                    ):
                        name, title = g1.strip(), g2.strip().title()
                    else:
                        name, title = g2.strip(), g1.strip().title()
                elif len(groups) == 1:
                    name, title = groups[0].strip(), "Owner"
                else:
                    continue

                # Basic validation
                parts = name.split()
                if len(parts) >= 2 and len(name) >= 5:
                    return {"owner_name": name, "owner_title": title}

        return None

    def _extract_rating(self, text: str) -> dict | None:
        """Extract Google rating and review count from search results."""
        rating_pattern = r'(\d\.\d)\s*(?:\(|·)\s*(\d[\d,]*)\s*(?:reviews?|ratings?)'
        match = re.search(rating_pattern, text, re.IGNORECASE)
        if match:
            try:
                return {
                    "google_rating": float(match.group(1)),
                    "google_review_count": int(match.group(2).replace(",", "")),
                }
            except (ValueError, TypeError):
                pass
        return None

    def _find_linkedin(self, business_name: str, owner_name: str) -> str | None:
        """Search Google for LinkedIn profile of the business owner."""
        query = f'site:linkedin.com/in/ "{owner_name}" "{business_name}"'
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=5"

        try:
            soup = self.http.get_soup(url, use_cache=False)
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "linkedin.com/in/" in href:
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]
                    parsed = urlparse(href)
                    if "/in/" in parsed.path:
                        return f"https://www.linkedin.com{parsed.path}".rstrip("/")
        except Exception:
            pass

        return None

    def close(self):
        self.http.close()
