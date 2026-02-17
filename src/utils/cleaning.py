"""Data cleaning and normalization utilities for lead data."""

from __future__ import annotations

import re
import logging

import phonenumbers

logger = logging.getLogger(__name__)

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

STATE_NAME_TO_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}


def clean_lead_data(data: dict) -> dict | None:
    """
    Clean and normalize a raw lead dict.
    Returns None if the lead doesn't meet minimum quality.
    """
    if not data.get("business_name"):
        return None

    # ── Filter dead / closed businesses ──
    biz_name = data.get("business_name", "")
    if re.search(r"\bCLOSED\b", biz_name, re.I):
        return None

    cleaned = {}

    # Business name
    cleaned["business_name"] = clean_text(data.get("business_name", ""))
    if not cleaned["business_name"]:
        return None

    # Phone
    cleaned["phone"] = normalize_phone(data.get("phone"))

    # Email
    cleaned["email"] = normalize_email(data.get("email"))

    # Website
    cleaned["website"] = normalize_url(data.get("website"))
    cleaned["has_website"] = bool(cleaned["website"])

    # Address
    cleaned["address"] = clean_text(data.get("address", ""))
    cleaned["city"] = clean_text(data.get("city", ""))
    cleaned["state"] = normalize_state(data.get("state", ""))
    cleaned["zip_code"] = normalize_zip(data.get("zip_code", ""))
    cleaned["country"] = "US"

    # Validate US location
    if cleaned["state"] and cleaned["state"] not in US_STATES:
        return None

    # Category
    cleaned["category"] = clean_text(data.get("category", ""))

    # Source
    cleaned["source"] = data.get("source", "unknown")
    cleaned["source_url"] = data.get("source_url")

    # Pass through optional fields
    optional_fields = [
        "subcategory", "owner_name", "owner_title", "employee_count",
        "year_established", "business_type", "google_rating",
        "google_review_count", "yelp_rating", "yelp_review_count",
        "bbb_rating", "bbb_accredited",
        "latitude", "longitude", "google_place_id", "business_hours",
        "photo_count", "price_level", "description", "service_options",
        "has_google_business_profile",
    ]
    for field in optional_fields:
        if data.get(field) is not None:
            cleaned[field] = data[field]

    # Quality score
    cleaned["quality_score"] = calculate_quality_score(cleaned)

    return cleaned


def clean_text(text: str) -> str:
    """Remove extra whitespace and normalize text."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    return text


def normalize_phone(phone: str) -> str | None:
    """Normalize US phone number to E.164 format."""
    if not phone:
        return None
    try:
        parsed = phonenumbers.parse(phone, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except phonenumbers.NumberParseException:
        pass
    # Fallback: just extract digits
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def normalize_email(email: str) -> str | None:
    """Validate and normalize email."""
    if not email:
        return None
    email = email.strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if re.match(pattern, email):
        return email
    return None


def normalize_url(url: str) -> str | None:
    """Normalize website URL."""
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    # Basic validation
    pattern = r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    if re.match(pattern, url):
        return url
    return None


def normalize_state(state: str) -> str:
    """Normalize state to 2-letter abbreviation."""
    if not state:
        return ""
    state = state.strip()
    if len(state) == 2:
        return state.upper()
    abbrev = STATE_NAME_TO_ABBREV.get(state.lower())
    return abbrev if abbrev else ""


def normalize_zip(zip_code: str) -> str:
    """Normalize US zip code."""
    if not zip_code:
        return ""
    digits = re.sub(r"\D", "", zip_code)
    if len(digits) >= 5:
        return digits[:5]
    return ""


def calculate_quality_score(lead: dict) -> int:
    """Calculate a 0-100 quality score for a lead.

    Heavily rewards finding the actual decision maker (owner, founder, etc.)
    and their personal contact info — not just generic info@.
    """
    score = 0

    # ── Core fields (max 40 points) ──
    if lead.get("business_name"):
        score += 8
    if lead.get("phone"):
        score += 10
    if lead.get("email"):
        email = lead["email"]
        local = email.split("@")[0].lower() if email else ""
        generic = {
            "info", "contact", "hello", "support", "admin", "sales",
            "billing", "office", "help", "service", "team",
        }
        if local in generic:
            score += 7    # generic email is worth less
        else:
            score += 12   # personal email is worth more
    if lead.get("address") and lead.get("city") and lead.get("state"):
        score += 10

    # ── Decision maker / owner info (max 30 points) ──
    if lead.get("owner_name"):
        score += 10
    if lead.get("owner_email"):
        score += 8
    if lead.get("owner_linkedin"):
        score += 5
    if lead.get("owner_title"):
        score += 3
    if lead.get("owner_phone"):
        score += 4

    # ── Business details (max 15 points) ──
    if lead.get("website"):
        score += 4
    if lead.get("category"):
        score += 3
    if lead.get("employee_count"):
        score += 4
    if lead.get("year_established"):
        score += 4

    # ── Online presence (max 15 points) ──
    if lead.get("google_rating"):
        score += 4
    if lead.get("yelp_rating"):
        score += 3
    social_fields = ["facebook_url", "instagram_url", "linkedin_url"]
    social_count = sum(1 for f in social_fields if lead.get(f))
    score += min(social_count * 3, 8)

    return min(score, 100)
