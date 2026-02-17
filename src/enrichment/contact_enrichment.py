"""Decision maker discovery — finds actual people (owners, managers) behind businesses."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# Common "about" or "team" page paths
ABOUT_PATHS = [
    "/about", "/about-us", "/about-me", "/our-team", "/team",
    "/staff", "/leadership", "/management", "/contact",
    "/contact-us", "/our-story", "/meet-the-team", "/who-we-are",
    "/our-company", "/bio", "/owner", "/founders",
]

# Title patterns for decision makers (ranked by importance)
DECISION_MAKER_TITLES = [
    "owner", "founder", "co-founder", "cofounder",
    "ceo", "president", "managing director",
    "principal", "proprietor", "partner", "managing partner",
    "general manager", "gm", "director", "manager",
    "chief executive", "chief operating", "coo", "cfo",
    "vice president", "vp",
]

EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE,
)

# Generic email prefixes that are NOT personal
GENERIC_PREFIXES = {
    "info", "contact", "hello", "support", "admin", "sales",
    "billing", "office", "help", "service", "team", "inquiries",
    "general", "mail", "enquiries", "reception", "accounts",
    "customerservice", "cs", "orders",
}

# Words that are NOT person names — US states, prepositions, common words
_NOT_NAMES = {
    # US state abbreviations
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    # Common false-positive words
    "of", "the", "and", "for", "all", "our", "your", "their",
    "this", "that", "from", "with", "about", "more", "best",
    "new", "old", "top", "big", "pro", "auto", "car", "llc",
    "inc", "corp", "ltd", "company", "service", "services",
    "mobile", "mesa", "phoenix", "tampa", "miami", "houston",
    "dallas", "austin", "atlanta", "orlando", "jacksonville",
    "naples", "sarasota", "fort", "west", "east", "north", "south",
    "saint", "san", "los", "las", "new", "port", "springs",
    "beach", "lake", "palm", "cape", "coral", "bay", "city",
    "downtown", "midtown", "uptown", "central", "metro",
}

# State Secretary of State / business registration search URLs
STATE_BIZ_SEARCH = {
    "FL": "https://www.google.com/search?q=site:sunbiz.org+{query}",
    "TX": "https://www.google.com/search?q=site:sos.state.tx.us+{query}",
    "CA": "https://www.google.com/search?q=site:bizfileonline.sos.ca.gov+{query}",
    "NY": "https://www.google.com/search?q=site:appext20.dos.ny.gov+{query}",
    "GA": "https://www.google.com/search?q=site:ecorp.sos.ga.gov+{query}",
    "OH": "https://www.google.com/search?q=site:businesssearch.ohiosos.gov+{query}",
    "NC": "https://www.google.com/search?q=site:sosnc.gov+{query}",
    "PA": "https://www.google.com/search?q=site:ecorp.dos.pa.gov+{query}",
    "IL": "https://www.google.com/search?q=site:ilsos.gov+{query}",
    "NJ": "https://www.google.com/search?q=site:njportal.com+{query}",
}


def _is_valid_person_name(name: str) -> bool:
    """Check if a string looks like a real person's name, not a place or junk."""
    if not name or len(name) < 5:
        return False

    parts = name.strip().split()
    if len(parts) < 2:
        return False

    # Each part must be at least 2 chars (initials with period are OK, e.g. "J.")
    for part in parts:
        clean = part.rstrip(".")
        if len(clean) < 2:
            # Allow single-letter initials with period
            if not (len(part) == 2 and part.endswith(".")):
                return False

    # Check for junk words
    for part in parts:
        if part.lower().rstrip(".") in _NOT_NAMES:
            return False

    # Must start with uppercase
    if not parts[0][0].isupper() or not parts[-1][0].isupper():
        return False

    # Reject all-caps (likely acronyms) and all-lowercase
    for part in parts:
        if part == part.upper() and len(part) > 2:
            return False

    return True


class ContactEnricher(BaseEnricher):
    """Find real decision makers — owners, founders, managers — not generic contacts."""

    MODULE_NAME = "contact_enrichment"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        result = {}
        name = lead.businessName or ""

        # Strategy 1: Mine the business website for owner info
        if lead.website:
            website_result = self._mine_website(lead)
            result.update(website_result)

        # Strategy 2: Google search for "business name owner" / "business name founder"
        # Skip if google_intel already found the owner (saves a Google search)
        existing_owner = getattr(lead, "ownerName", None)
        if not result.get("owner_name") and not existing_owner:
            google_result = self._google_owner_search(lead)
            result.update(google_result)

        # Strategy 3: Check state business registrations for registered agent/officer
        # Skip if owner already found by any prior strategy or module
        effective_owner = result.get("owner_name") or existing_owner
        if not effective_owner and lead.state:
            reg_result = self._check_state_registration(name, lead.state)
            result.update(reg_result)

        # Strategy 4: Search Google for LinkedIn profile
        existing_linkedin = result.get("owner_linkedin") or getattr(lead, "ownerLinkedin", None)
        if not existing_linkedin:
            owner_name_for_search = result.get("owner_name") or getattr(lead, "ownerName", None)
            linkedin = self._find_linkedin(name, lead.city, lead.state, owner_name_for_search)
            if linkedin:
                result["owner_linkedin"] = linkedin

        # Strategy 5: Generate personal email from owner name + business domain
        effective_owner_name = result.get("owner_name") or getattr(lead, "ownerName", None)
        existing_owner_email = result.get("owner_email") or getattr(lead, "ownerEmail", None)
        if effective_owner_name and lead.website and not existing_owner_email:
            personal_email = self._generate_personal_email(
                effective_owner_name, lead.website
            )
            if personal_email:
                result["owner_email"] = personal_email

        # Strategy 6: Promote personal email to main email if current is generic
        # Check both what we found AND what previous modules set on the lead
        owner_email = result.get("owner_email") or getattr(lead, "ownerEmail", None)
        if owner_email:
            current_email = lead.email or ""
            current_local = current_email.split("@")[0].lower() if current_email else ""

            # If the lead has no email or only a generic one, promote the personal email
            if not current_email or current_local in GENERIC_PREFIXES:
                result["email"] = owner_email
                logger.debug(
                    f"[Contact] Promoted personal email for {name}: "
                    f"{owner_email} (was: {current_email or 'none'})"
                )

        if result.get("owner_name"):
            logger.debug(
                f"[Contact] Found decision maker for {name}: "
                f"{result.get('owner_name')} ({result.get('owner_title', 'Unknown')})"
            )

        return result

    def _mine_website(self, lead) -> dict:
        """Deep mine the business website for owner/decision maker info."""
        result = {}
        soups_to_check = []

        # Fetch homepage
        try:
            homepage = self.http.get_soup(lead.website)
            soups_to_check.append(("homepage", homepage))
        except Exception:
            return {}

        # Find and fetch about/team pages
        base_url = lead.website.rstrip("/")
        for path in ABOUT_PATHS:
            try:
                url = base_url + path
                soup = self.http.get_soup(url)
                # Only keep if it's a real page (not a redirect to homepage)
                text = soup.get_text()
                if len(text) > 500:
                    soups_to_check.append((path, soup))
                    if len(soups_to_check) >= 5:
                        break
            except Exception:
                continue

        # Check each page for owner info
        for page_name, soup in soups_to_check:
            owner_info = self._extract_person_from_page(soup)
            if owner_info.get("owner_name"):
                result.update(owner_info)
                break

        # Also extract any personal emails from all pages
        if not result.get("owner_email"):
            for _, soup in soups_to_check:
                personal_email = self._find_personal_email(soup, lead.website)
                if personal_email:
                    result["owner_email"] = personal_email
                    break

        return result

    def _extract_person_from_page(self, soup: BeautifulSoup) -> dict:
        """Extract person name + title from a page using multiple strategies."""
        result = {}
        page_text = soup.get_text(separator=" ")

        # Strategy A: Schema.org / JSON-LD structured data (most reliable)
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string)
                person = self._person_from_jsonld(data)
                if person:
                    return person
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        # Strategy B: Look for people in structured HTML elements
        # Team/about sections often use cards or list items
        person_containers = soup.select(
            ".team-member, .staff-member, .bio, .founder, .owner, "
            ".about-author, .leadership, [class*='team'], [class*='bio'], "
            "[class*='staff'], [class*='owner'], [class*='founder'], "
            "[class*='about-us'] .member, [class*='personnel']"
        )
        for container in person_containers:
            text = container.get_text(separator=" ")
            name_match = re.search(
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', text
            )
            if name_match:
                name = name_match.group(1)
                if _is_valid_person_name(name):
                    title = self._find_title_near_name(text, name)
                    if title:
                        return {"owner_name": name, "owner_title": title.title()}

        # Strategy C: Title pattern matching in page text
        title_pattern = "|".join(re.escape(t) for t in DECISION_MAKER_TITLES)
        patterns = [
            # "John Smith, Owner" / "John Smith - Founder"
            rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[,\-–—|/]\s*({title_pattern})',
            # "Owner: John Smith" / "Founder — John Smith"
            rf'({title_pattern})\s*[:\-–—|/]\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "Meet our Owner John Smith" / "About Founder John Smith"
            rf'(?:meet\s+(?:our\s+)?|about\s+|by\s+)({title_pattern})\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "John Smith is the owner of..."
            rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s+is\s+the\s+({title_pattern})',
            # "owned by John Smith"
            rf'(?:owned|founded|started|operated)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                candidate_name = None
                candidate_title = None

                if len(groups) == 2:
                    g1, g2 = groups
                    if re.match(r'[A-Z][a-z]+', g1) and not any(
                        t in g1.lower() for t in DECISION_MAKER_TITLES
                    ):
                        candidate_name = g1.strip()
                        candidate_title = g2.strip().title()
                    else:
                        candidate_name = g2.strip()
                        candidate_title = g1.strip().title()
                elif len(groups) == 1:
                    candidate_name = groups[0].strip()
                    candidate_title = "Owner"

                if candidate_name and _is_valid_person_name(candidate_name):
                    result["owner_name"] = candidate_name
                    result["owner_title"] = candidate_title
                    break

        # Strategy D: Look for a name associated with a photo/headshot
        if not result.get("owner_name"):
            for img in soup.select("img[alt]"):
                alt = img.get("alt", "")
                # Check if alt text looks like a person's name
                name_match = re.match(
                    r'^([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*[-,]\s*(.+))?$', alt
                )
                if name_match:
                    name = name_match.group(1)
                    title = name_match.group(2) or ""
                    if _is_valid_person_name(name) and title and any(
                        t in title.lower() for t in DECISION_MAKER_TITLES
                    ):
                        result["owner_name"] = name
                        result["owner_title"] = title.strip().title()
                        break

        return result

    def _person_from_jsonld(self, data, depth=0) -> dict | None:
        """Extract person from JSON-LD structured data."""
        if depth > 5:
            return None
        if isinstance(data, dict):
            # Check for Person type
            schema_type = data.get("@type", "")
            if isinstance(schema_type, str) and schema_type.lower() == "person":
                name = data.get("name")
                if name and _is_valid_person_name(name):
                    return {
                        "owner_name": name,
                        "owner_title": data.get("jobTitle", "Owner"),
                        "owner_email": data.get("email"),
                    }

            # Check for founder/employee/member
            for key in ("founder", "employee", "member", "author", "creator"):
                val = data.get(key)
                if isinstance(val, dict):
                    person = self._person_from_jsonld(val, depth + 1)
                    if person:
                        return person
                elif isinstance(val, list):
                    for item in val:
                        person = self._person_from_jsonld(item, depth + 1)
                        if person:
                            return person

        elif isinstance(data, list):
            for item in data:
                person = self._person_from_jsonld(item, depth + 1)
                if person:
                    return person
        return None

    def _find_title_near_name(self, text: str, name: str) -> str | None:
        """Find a decision maker title near a name in text."""
        # Look within ~50 chars of the name
        idx = text.find(name)
        if idx < 0:
            return None
        context = text[max(0, idx - 50): idx + len(name) + 100].lower()
        for title in DECISION_MAKER_TITLES:
            if title in context:
                return title
        return None

    def _find_personal_email(self, soup: BeautifulSoup, website: str) -> str | None:
        """Find a personal (non-generic) email from a page."""
        domain = urlparse(website).netloc.replace("www.", "")
        page_text = soup.get_text(separator=" ")
        emails = EMAIL_RE.findall(page_text)

        # Also check mailto links
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email:
                emails.append(email)

        for email in emails:
            email = email.lower()
            local = email.split("@")[0]
            email_domain = email.split("@")[1] if "@" in email else ""

            # Skip generic prefixes
            if local in GENERIC_PREFIXES:
                continue
            # Prefer emails from the business domain
            if domain in email_domain:
                # Check if it looks personal (has a name-like prefix)
                if re.match(r'^[a-z]+\.?[a-z]+$', local) and len(local) > 2:
                    return email

        return None

    def _google_owner_search(self, lead) -> dict:
        """Google search for the business owner/founder.

        Limited to 1 query to conserve Google request budget.
        """
        name = lead.businessName or ""
        city = lead.city or ""
        state = lead.state or ""

        # Single combined query — saves Google budget
        queries = [
            f'"{name}" owner OR founder {city} {state}',
        ]

        for query in queries:
            try:
                url = f"https://www.google.com/search?q={quote_plus(query)}&num=10"
                soup = self.http.get_soup(url)
                text = soup.get_text(separator=" ")

                # Look for "Owner: Name" or "Name, Owner" patterns in Google snippets
                patterns = [
                    rf'(?:owner|founded|owned\s+by)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
                    rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[,\-–]\s*(?:owner|founder)',
                    rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s+(?:is|was)\s+the\s+(?:owner|founder)',
                ]

                for pattern in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        owner_name = match.group(1).strip()
                        if _is_valid_person_name(owner_name):
                            return {
                                "owner_name": owner_name,
                                "owner_title": "Owner",
                            }
            except Exception:
                continue

        return {}

    def _check_state_registration(self, business_name: str, state: str) -> dict:
        """Check state Secretary of State business registration for officer names."""
        state = state.upper()

        # Use Google to search the state's business registry
        query = f"{business_name} {state} business registration officer"
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=10"

        try:
            soup = self.http.get_soup(url)
            text = soup.get_text(separator=" ")

            # Look for officer/agent patterns
            patterns = [
                r'(?:registered\s+agent|officer|director|incorporator)[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
                r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[,\-]\s*(?:registered\s+agent|officer|director)',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    if _is_valid_person_name(name):
                        return {
                            "owner_name": name,
                            "owner_title": "Owner",
                        }
        except Exception:
            pass

        return {}

    def _find_linkedin(
        self, business_name: str, city: str | None, state: str | None,
        owner_name: str | None
    ) -> str | None:
        """Find a LinkedIn profile for the business owner."""
        if owner_name:
            query = f'site:linkedin.com/in/ "{owner_name}" "{business_name}"'
        else:
            query = f'site:linkedin.com/in/ "{business_name}" owner {city or ""} {state or ""}'

        url = f"https://www.google.com/search?q={quote_plus(query)}&num=5"

        try:
            soup = self.http.get_soup(url)
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "linkedin.com/in/" in href:
                    # Extract clean LinkedIn URL
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=")[1].split("&")[0]
                    parsed = urlparse(href)
                    if "/in/" in parsed.path:
                        clean = f"https://www.linkedin.com{parsed.path}".rstrip("/")
                        return clean
        except Exception:
            pass

        return None

    def _generate_personal_email(self, owner_name: str, website: str) -> str | None:
        """Generate likely personal email from owner name + business domain."""
        parsed = urlparse(website)
        domain = parsed.netloc.replace("www.", "")

        if not domain or "." not in domain:
            return None

        # Skip platform domains
        platform_domains = {
            "wixsite.com", "squarespace.com", "weebly.com",
            "godaddysites.com", "business.site", "wordpress.com",
            "myshopify.com", "webflow.io",
        }
        if any(p in domain for p in platform_domains):
            return None

        # Parse name parts
        parts = owner_name.strip().split()
        if len(parts) < 2:
            return None

        first = parts[0].lower()
        last = parts[-1].lower()

        # Skip if parts look wrong (initials only, etc.)
        if len(first) < 2 or len(last) < 2:
            return None

        # Return the most common small-business email pattern
        # firstname@domain is by far the most common for owner-operated businesses
        return f"{first}@{domain}"

    def close(self):
        self.http.close()
