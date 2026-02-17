"""ICP (Ideal Customer Profile) lead scoring module.

Scores leads on business fit — not just data completeness.
Unlike quality_score which measures "how much data do we have?",
icp_score measures "how good of a prospect is this business?"

Scoring dimensions:
  1. Reachability   (35 pts) — Can we actually contact the decision maker?
  2. Business Health (25 pts) — Is this a real, active, reputable business?
  3. Digital Presence (20 pts) — How sophisticated is their online presence?
  4. Opportunity Signals (20 pts) — Signs they might need services
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.enrichment.base import BaseEnricher

logger = logging.getLogger(__name__)

# Generic email prefixes that indicate no personal contact found
GENERIC_EMAIL_PREFIXES = {
    "info", "contact", "hello", "support", "admin", "sales",
    "billing", "office", "help", "service", "team", "enquiry",
    "inquiry", "general", "mail", "webmaster", "noreply",
}


class ICPScoringEnricher(BaseEnricher):
    """Calculate ICP (Ideal Customer Profile) score for a lead."""

    MODULE_NAME = "icp_scoring"

    def enrich(self, lead) -> dict:
        """Calculate and return the ICP score for a lead."""
        score = calculate_icp_score(lead)
        return {"icp_score": score}


def calculate_icp_score(lead) -> int:
    """
    Calculate ICP score (0-100) based on prospect quality, not data completeness.

    This scores how VALUABLE a lead is as a prospect, considering:
    - Can we reach the decision maker directly?
    - Is this a healthy, active business?
    - Do they have digital sophistication (or lack thereof = opportunity)?
    - Are there buying signals?
    """
    score = 0

    # ── 1. REACHABILITY (max 35 points) ──
    # Can we actually reach the right person?

    # Owner/decision maker found (10 pts)
    owner_name = _get(lead, "ownerName", "owner_name")
    if owner_name:
        score += 10

    # Personal email — not generic (10 pts for personal, 3 pts for generic)
    owner_email = _get(lead, "ownerEmail", "owner_email")
    main_email = _get(lead, "email")
    if owner_email:
        score += 10
    elif main_email:
        local = main_email.split("@")[0].lower() if main_email else ""
        if local not in GENERIC_EMAIL_PREFIXES:
            score += 8  # personal email in main field
        else:
            score += 3  # generic email is something, but not great

    # Direct phone available (8 pts)
    phone = _get(lead, "phone")
    owner_phone = _get(lead, "ownerPhone", "owner_phone")
    if owner_phone:
        score += 8
    elif phone:
        score += 5

    # LinkedIn profile found (7 pts)
    owner_linkedin = _get(lead, "ownerLinkedin", "owner_linkedin")
    if owner_linkedin:
        score += 7

    # ── 2. BUSINESS HEALTH (max 25 points) ──
    # Is this a real, active, reputable business?

    # Google rating (max 8 pts)
    google_rating = _get(lead, "googleRating", "google_rating")
    if google_rating:
        try:
            rating = float(google_rating)
            if rating >= 4.5:
                score += 8
            elif rating >= 4.0:
                score += 6
            elif rating >= 3.5:
                score += 4
            elif rating >= 3.0:
                score += 2
            # Below 3.0: no points (risky business)
        except (ValueError, TypeError):
            pass

    # Review count — more reviews = more established (max 7 pts)
    google_reviews = _get(lead, "googleReviewCount", "google_review_count")
    if google_reviews:
        try:
            count = int(google_reviews)
            if count >= 100:
                score += 7
            elif count >= 50:
                score += 5
            elif count >= 20:
                score += 3
            elif count >= 5:
                score += 1
        except (ValueError, TypeError):
            pass

    # Years in business (max 5 pts)
    year_est = _get(lead, "yearEstablished", "year_established")
    if year_est:
        try:
            years = datetime.now().year - int(year_est)
            if years >= 10:
                score += 5
            elif years >= 5:
                score += 4
            elif years >= 2:
                score += 3
            elif years >= 1:
                score += 1
        except (ValueError, TypeError):
            pass

    # BBB accredited (3 pts)
    bbb = _get(lead, "bbbAccredited", "bbb_accredited")
    if bbb:
        score += 3

    # Has a physical address (2 pts)
    address = _get(lead, "address")
    city = _get(lead, "city")
    state = _get(lead, "state")
    if address and city and state:
        score += 2

    # ── 3. DIGITAL PRESENCE (max 20 points) ──
    # How sophisticated is their online presence?

    # Has website (4 pts)
    website = _get(lead, "website")
    has_website = _get(lead, "hasWebsite", "has_website")
    if website or has_website:
        score += 4

    # SSL + mobile friendly = modern site (3 pts)
    has_ssl = _get(lead, "hasSsl", "has_ssl")
    mobile = _get(lead, "mobileFriendly", "mobile_friendly")
    if has_ssl:
        score += 1
    if mobile:
        score += 2

    # Social media presence (max 5 pts)
    social_fields = [
        ("facebookUrl", "facebook_url"),
        ("instagramUrl", "instagram_url"),
        ("linkedinUrl", "linkedin_url"),
        ("twitterUrl", "twitter_url"),
        ("youtubeUrl", "youtube_url"),
        ("tiktokUrl", "tiktok_url"),
    ]
    social_count = sum(1 for camel, snake in social_fields if _get(lead, camel, snake))
    score += min(social_count * 2, 5)

    # Google Business Profile (3 pts)
    gbp = _get(lead, "hasGoogleBusinessProfile", "has_google_business_profile")
    if gbp:
        score += 3

    # Already running ads = has marketing budget (5 pts)
    runs_google = _get(lead, "runsGoogleAds", "runs_google_ads")
    runs_fb = _get(lead, "runsFacebookAds", "runs_facebook_ads")
    if runs_google and runs_fb:
        score += 5
    elif runs_google or runs_fb:
        score += 3

    # ── 4. OPPORTUNITY SIGNALS (max 20 points) ──
    # Signs they might need services / are a good fit for outreach

    # No website = needs web services (5 pts if they DON'T have one)
    if not website and not has_website:
        score += 5

    # Outdated website platform = upgrade opportunity (4 pts)
    platform = _get(lead, "websitePlatform", "website_platform")
    if platform:
        platform_lower = str(platform).lower()
        outdated = {"weebly", "godaddy", "jimdo", "blogger", "homestead", "tripod"}
        if platform_lower in outdated:
            score += 4

    # Low rating but has reviews = needs reputation help (3 pts)
    if google_rating:
        try:
            if float(google_rating) < 3.5 and google_reviews and int(google_reviews) > 5:
                score += 3
        except (ValueError, TypeError):
            pass

    # No social media = needs social marketing (4 pts)
    if social_count == 0:
        score += 4

    # Not running any ads but has a website = advertising opportunity (4 pts)
    if (website or has_website) and not runs_google and not runs_fb:
        score += 4

    return min(score, 100)


def _get(lead, *field_names):
    """Get a field value from a lead object, trying multiple field name variants."""
    for name in field_names:
        val = getattr(lead, name, None)
        if val is not None:
            return val
    return None
