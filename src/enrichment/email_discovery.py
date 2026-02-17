"""Email discovery enrichment — finds business emails via multiple strategies.

Prioritizes personal emails (john@company.com) over generic ones (info@company.com).
Generic emails are only set as a last resort — the contact_enrichment module will
upgrade them to personal emails when it discovers the owner's name.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus, urlparse

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

JUNK_DOMAINS = {
    "example.com", "domain.com", "email.com", "test.com",
    "sentry.io", "wixpress.com", "wordpress.com",
    "squarespace.com", "w3.org", "schema.org", "googleapis.com",
    "google.com", "google.de", "google.co.uk", "google.ca",
    "google.com.au", "google.co.in",
    "facebook.com", "twitter.com", "gstatic.com",
    "sonsio.com", "shell.com",
    "yelp.com", "bbb.org", "yellowpages.com",
}

# Generic prefixes we deprioritize — we want real people's emails
GENERIC_PREFIXES = {
    "info", "contact", "hello", "support", "admin", "sales",
    "billing", "office", "help", "service", "team", "inquiries",
    "general", "mail", "enquiries", "reception", "accounts",
    "customerservice", "cs", "orders", "noreply", "no-reply",
}


def _is_junk_email_domain(domain: str) -> bool:
    """Check if an email domain is junk (Google, social media, platform, etc)."""
    if domain in JUNK_DOMAINS:
        return True
    # Catch all Google country domains (google.de, google.fr, google.co.uk, etc)
    if domain.startswith("google.") or ".google." in domain:
        return True
    return False


def _is_personal_email(email: str) -> bool:
    """Check if an email looks personal (not generic like info@)."""
    local = email.split("@")[0].lower()
    return local not in GENERIC_PREFIXES


class EmailDiscoveryEnricher(BaseEnricher):
    """Discover email addresses — strongly prefers personal over generic."""

    MODULE_NAME = "email_discovery"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        # Skip if email already known AND it's personal
        if lead.email and _is_personal_email(lead.email):
            return {}

        name = lead.businessName or ""
        city = lead.city or ""
        state = lead.state or ""
        phone = lead.phone or ""

        if not name:
            return {}

        personal_emails = []  # personal ones we find
        generic_emails = []   # info@, contact@, etc.

        # ── Website-first strategies (no Google, no rate limits) ──

        # Strategy 1: Mine the website for all emails
        if lead.website:
            p, g = self._mine_website_emails(lead.website)
            personal_emails.extend(p)
            generic_emails.extend(g)

        # ── Google strategies (limited budget: max 2 queries) ──

        # Strategy 2: Google search for the business email (only if website had nothing)
        if not personal_emails and not generic_emails:
            found = self._google_email_search(name, city, state)
            if found:
                (personal_emails if _is_personal_email(found) else generic_emails).append(found)

        # Strategy 3: Google with "business name email" (only if still nothing)
        if not personal_emails and not generic_emails:
            found = self._google_email_search(f'"{name}" email', city, state)
            if found:
                (personal_emails if _is_personal_email(found) else generic_emails).append(found)

        result = {}

        # Strongly prefer personal email
        if personal_emails:
            email = personal_emails[0]
            logger.debug(f"[EmailDiscovery] Found PERSONAL email for {name}: {email}")
            result["email"] = email
        elif generic_emails and not lead.email:
            # Only set generic if we have nothing at all
            email = generic_emails[0]
            logger.debug(f"[EmailDiscovery] Found generic email for {name}: {email}")
            result["email"] = email

        return result

    def _google_email_search(self, query: str, city: str, state: str) -> str | None:
        """Search Google for email addresses associated with the business."""
        search_query = f"{query} {city} {state} email contact".strip()
        url = f"https://www.google.com/search?q={quote_plus(search_query)}&num=10"

        try:
            soup = self.http.get_soup(url)
        except Exception as e:
            logger.debug(f"[EmailDiscovery] Google search failed: {e}")
            return None

        page_text = soup.get_text(separator=" ")
        emails = EMAIL_RE.findall(page_text)

        # Return first valid email (personal emails rise to top naturally from Google)
        for email in emails:
            email = email.lower()
            domain = email.split("@")[1] if "@" in email else ""
            if not _is_junk_email_domain(domain) and len(email) < 50:
                return email

        return None

    def _mine_website_emails(self, website: str) -> tuple[list, list]:
        """Scrape the website for all emails, separated into personal vs generic."""
        personal = []
        generic = []

        try:
            soup = self.http.get_soup(website)
        except Exception:
            return personal, generic

        # Gather emails from page text
        page_text = soup.get_text(separator=" ")
        all_emails = EMAIL_RE.findall(page_text)

        # Also check mailto links
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                all_emails.append(email)

        parsed = urlparse(website)
        biz_domain = parsed.netloc.replace("www.", "")

        seen = set()
        for email in all_emails:
            email = email.lower()
            if email in seen:
                continue
            seen.add(email)

            domain = email.split("@")[1] if "@" in email else ""
            if _is_junk_email_domain(domain):
                continue
            if len(email) > 50:
                continue

            # Prefer emails on the business domain
            if biz_domain and biz_domain in domain:
                if _is_personal_email(email):
                    personal.append(email)
                else:
                    generic.append(email)
            else:
                # Off-domain email — still capture if personal-looking
                if _is_personal_email(email):
                    personal.append(email)

        return personal, generic

    def _check_domain_patterns(self, website: str) -> str | None:
        """Search Google for common name-based email patterns on the domain."""
        parsed = urlparse(website)
        domain = parsed.netloc.replace("www.", "")

        if not domain or "." not in domain:
            return None

        # Skip platform domains
        platform_domains = {
            "wixsite.com", "squarespace.com", "weebly.com",
            "godaddysites.com", "business.site", "wordpress.com",
            "myshopify.com", "webflow.io", "carrd.co",
        }
        if any(platform in domain for platform in platform_domains):
            return None

        # Search for any personal email at this domain
        search_query = f'"@{domain}" -info -contact -hello -support -admin -sales'
        url = f"https://www.google.com/search?q={quote_plus(search_query)}&num=10"

        try:
            soup = self.http.get_soup(url)
            page_text = soup.get_text(separator=" ")
            emails = EMAIL_RE.findall(page_text)

            for email in emails:
                email = email.lower()
                if domain in email and _is_personal_email(email):
                    return email
        except Exception:
            pass

        return None

    def _search_directories(self, name: str, city: str, state: str) -> str | None:
        """Search business directories for email addresses."""
        # Search Manta (often has emails)
        search_query = f"site:manta.com {name} {city} {state}"
        url = f"https://www.google.com/search?q={quote_plus(search_query)}&num=5"

        try:
            soup = self.http.get_soup(url)

            # Find Manta result links
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "manta.com" in href and "/c/" in href:
                    manta_url = href
                    if manta_url.startswith("/url?q="):
                        manta_url = manta_url.split("/url?q=")[1].split("&")[0]

                    try:
                        manta_soup = self.http.get_soup(manta_url)
                        page_text = manta_soup.get_text(separator=" ")
                        emails = EMAIL_RE.findall(page_text)
                        for email in emails:
                            domain = email.split("@")[1].lower()
                            if domain not in JUNK_DOMAINS and "manta" not in domain:
                                return email.lower()
                    except Exception:
                        pass
                    break
        except Exception as e:
            logger.debug(f"[EmailDiscovery] Directory search failed: {e}")

        return None

    def close(self):
        self.http.close()
