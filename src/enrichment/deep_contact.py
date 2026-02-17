"""Deep contact crawler — follows internal links to find hidden emails, phones, and contacts."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# Pages most likely to have contact info
PRIORITY_PATHS = [
    "/contact", "/contact-us", "/contactus", "/get-in-touch",
    "/about", "/about-us", "/aboutus", "/our-team", "/team",
    "/staff", "/leadership", "/management",
    "/our-story", "/our-company", "/who-we-are",
    "/services", "/careers", "/jobs", "/privacy",
    "/footer", "/sitemap",
]

# Email regex
EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

# Phone regex (US formats)
PHONE_RE = re.compile(
    r'(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}'
)

# Obfuscated email patterns (e.g., "info [at] company [dot] com")
OBFUSCATED_EMAIL_RE = re.compile(
    r'([a-zA-Z0-9._%+-]+)\s*[\[\(]\s*(?:at|AT)\s*[\]\)]\s*'
    r'([a-zA-Z0-9.-]+)\s*[\[\(]\s*(?:dot|DOT)\s*[\]\)]\s*'
    r'([a-zA-Z]{2,})',
)

# Junk emails to ignore
JUNK_EMAIL_DOMAINS = {
    "example.com", "domain.com", "email.com", "test.com",
    "sentry.io", "wixpress.com", "wordpress.com",
    "squarespace.com", "godaddy.com", "weebly.com", "wix.com",
    "shopify.com", "googleapis.com", "gravatar.com", "w3.org",
    "schema.org", "facebook.com", "twitter.com", "instagram.com",
    "cloudflare.com", "google.com", "gstatic.com", "jquery.com",
    "bootstrapcdn.com", "jsdelivr.net", "unpkg.com", "cdnjs.com",
    "fontawesome.com", "sonsio.com", "shell.com",
}

JUNK_EMAIL_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "webmaster", "hostmaster",
    "abuse", "test", "null", "devnull", "root", "user",
}


class DeepContactEnricher(BaseEnricher):
    """Crawl a business website deeply to find all contact information."""

    MODULE_NAME = "deep_contact"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        if not lead.website:
            return {}

        result = {}
        all_emails = set()
        all_phones = set()
        pages_crawled = 0
        max_pages = 2  # Only crawl top 2 priority pages (contact + about)

        base_url = lead.website.rstrip("/")
        base_domain = urlparse(base_url).netloc.lower()

        # Step 1: Crawl the homepage
        try:
            homepage_soup = self.http.get_soup(base_url)
            self._extract_from_page(homepage_soup, all_emails, all_phones)
            pages_crawled += 1
        except Exception as e:
            logger.debug(f"[DeepContact] Homepage failed for {base_url}: {e}")
            return {}

        # Step 2: Find and crawl internal links (priority pages first)
        internal_links = self._find_internal_links(homepage_soup, base_url, base_domain)

        # Sort: priority paths first
        def link_priority(url: str) -> int:
            path = urlparse(url).path.lower().rstrip("/")
            for i, priority_path in enumerate(PRIORITY_PATHS):
                if path == priority_path or path.endswith(priority_path):
                    return i
            return 999

        internal_links.sort(key=link_priority)

        for link_url in internal_links[:max_pages]:
            try:
                soup = self.http.get_soup(link_url)
                self._extract_from_page(soup, all_emails, all_phones)
                pages_crawled += 1
                # Early exit: stop crawling once we have enough data
                if len(all_emails) >= 2 and len(all_phones) >= 1:
                    break
            except Exception:
                continue

        # Step 3: Check for obfuscated emails on homepage
        if homepage_soup:
            self._extract_obfuscated_emails(homepage_soup, all_emails)

        # Step 4: Check for JavaScript-rendered email (common anti-scrape)
        if homepage_soup:
            self._extract_js_emails(homepage_soup, all_emails)

        # Step 5: Process results
        clean_emails = self._filter_emails(all_emails, base_domain)
        clean_phones = self._filter_phones(all_phones, lead.phone)

        if clean_emails:
            # Classify emails
            business_email, owner_email = self._classify_emails(clean_emails)
            if business_email and not lead.email:
                result["email"] = business_email
            if owner_email and not lead.ownerEmail:
                result["owner_email"] = owner_email
            # If we still don't have a main email, use the first one
            if not lead.email and not result.get("email") and clean_emails:
                result["email"] = clean_emails[0]

        if clean_phones:
            # If lead has no phone, use first found
            if not lead.phone:
                result["phone"] = clean_phones[0]

        logger.debug(
            f"[DeepContact] {lead.businessName}: crawled {pages_crawled} pages, "
            f"found {len(clean_emails)} emails, {len(clean_phones)} phones"
        )

        return result

    def _find_internal_links(
        self, soup: BeautifulSoup, base_url: str, base_domain: str
    ) -> list[str]:
        """Find all internal links on the page."""
        links = set()
        for a in soup.select("a[href]"):
            href = a.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Only follow internal links
            if parsed.netloc.lower().replace("www.", "") != base_domain.replace("www.", ""):
                continue

            # Skip media/assets
            ext = parsed.path.split(".")[-1].lower() if "." in parsed.path else ""
            if ext in ("pdf", "jpg", "jpeg", "png", "gif", "svg", "css", "js", "mp4", "mp3", "zip"):
                continue

            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            links.add(clean.rstrip("/"))

        # Remove the base URL itself
        links.discard(base_url.rstrip("/"))
        return list(links)

    def _extract_from_page(
        self, soup: BeautifulSoup, emails: set, phones: set
    ) -> None:
        """Extract emails and phones from a page."""
        page_text = soup.get_text(separator=" ")

        # Emails from text
        for email in EMAIL_RE.findall(page_text):
            emails.add(email.lower())

        # Emails from mailto: links
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                emails.add(email.lower())

        # Phones from text
        for phone in PHONE_RE.findall(page_text):
            phones.add(phone.strip())

        # Phones from tel: links
        for a in soup.select('a[href^="tel:"]'):
            href = a.get("href", "")
            phone = href.replace("tel:", "").replace("+1", "").strip()
            phone = re.sub(r"[^\d]", "", phone)
            if len(phone) == 10:
                phones.add(phone)

        # Check meta tags for contact info
        for meta in soup.select("meta"):
            content = meta.get("content", "")
            name = meta.get("name", "").lower()
            if name in ("email", "contact-email"):
                emails.add(content.lower())
            for email in EMAIL_RE.findall(content):
                emails.add(email.lower())

        # Check schema.org / JSON-LD
        import json
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string)
                self._extract_from_jsonld(data, emails, phones)
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

    def _extract_from_jsonld(self, data, emails: set, phones: set) -> None:
        """Recursively extract emails/phones from JSON-LD structured data."""
        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = key.lower()
                if isinstance(value, str):
                    if "email" in key_lower and "@" in value:
                        emails.add(value.lower())
                    elif "phone" in key_lower or "telephone" in key_lower:
                        clean = re.sub(r"[^\d]", "", value)
                        if len(clean) >= 10:
                            phones.add(clean[-10:])
                elif isinstance(value, (dict, list)):
                    self._extract_from_jsonld(value, emails, phones)
        elif isinstance(data, list):
            for item in data:
                self._extract_from_jsonld(item, emails, phones)

    def _extract_obfuscated_emails(self, soup: BeautifulSoup, emails: set) -> None:
        """Find emails that are obfuscated like 'info [at] company [dot] com'."""
        page_text = soup.get_text(separator=" ")
        for match in OBFUSCATED_EMAIL_RE.finditer(page_text):
            email = f"{match.group(1)}@{match.group(2)}.{match.group(3)}".lower()
            emails.add(email)

    def _extract_js_emails(self, soup: BeautifulSoup, emails: set) -> None:
        """Extract emails that are split across JavaScript variables."""
        for script in soup.select("script:not([src])"):
            text = script.string or ""
            # Look for patterns like: var email = "user" + "@" + "domain.com"
            concat_pattern = re.compile(
                r'''["']([a-zA-Z0-9._%+-]+)["']\s*\+\s*["']@["']\s*\+\s*["']([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})["']'''
            )
            for match in concat_pattern.finditer(text):
                email = f"{match.group(1)}@{match.group(2)}".lower()
                emails.add(email)

            # Also search for plain emails in inline scripts
            for email in EMAIL_RE.findall(text):
                if "@" in email and "." in email.split("@")[1]:
                    emails.add(email.lower())

    def _filter_emails(self, emails: set, base_domain: str) -> list[str]:
        """Filter out junk emails and return sorted by relevance."""
        filtered = []
        for email in emails:
            local, domain = email.split("@", 1) if "@" in email else ("", "")
            if not local or not domain:
                continue
            # Skip junk domains
            if domain in JUNK_EMAIL_DOMAINS:
                continue
            # Skip junk prefixes
            if local in JUNK_EMAIL_PREFIXES:
                continue
            # Skip image file extensions
            if domain.endswith((".png", ".jpg", ".gif", ".svg")):
                continue
            # Skip very long emails (probably not real)
            if len(email) > 60:
                continue
            filtered.append(email)

        # Sort: prefer emails from the business domain
        base_clean = base_domain.replace("www.", "")

        def email_score(email: str) -> int:
            domain = email.split("@")[1]
            local = email.split("@")[0].lower()
            score = 0
            # Prefer emails from the business domain
            if base_clean in domain:
                score -= 100
            # Prefer personal-looking emails
            if local not in ("info", "contact", "hello", "support", "admin", "sales", "billing"):
                score -= 10
            return score

        filtered.sort(key=email_score)
        return filtered

    def _filter_phones(self, phones: set, existing_phone: str | None) -> list[str]:
        """Filter and deduplicate phone numbers."""
        existing_digits = re.sub(r"[^\d]", "", existing_phone or "")
        result = []
        seen = set()
        for phone in phones:
            digits = re.sub(r"[^\d]", "", phone)
            # Normalize to 10 digits
            if len(digits) == 11 and digits.startswith("1"):
                digits = digits[1:]
            if len(digits) != 10:
                continue
            # Skip existing phone
            if digits == existing_digits:
                continue
            if digits not in seen:
                seen.add(digits)
                # Format nicely
                result.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
        return result

    def _classify_emails(self, emails: list[str]) -> tuple[str | None, str | None]:
        """Split emails into business (info@, contact@) and owner (personal) emails."""
        business = None
        owner = None
        for email in emails:
            local = email.split("@")[0].lower()
            if local in ("info", "contact", "hello", "support", "admin", "sales", "inquiries", "mail"):
                if not business:
                    business = email
            else:
                if not owner:
                    owner = email
        return business, owner

    def close(self):
        self.http.close()
