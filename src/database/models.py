"""
Prisma models are auto-generated from prisma/schema.prisma.
This module re-exports them for convenience and provides field mapping helpers.

Run `prisma generate` to regenerate the client after schema changes.
"""

from __future__ import annotations

import json as _json

# Fields that are stored as Json type in Prisma and need serialization
_JSON_FIELDS = {"techStack", "businessHours", "serviceOptions"}

# Mapping from snake_case (used in scrapers/cleaning) to camelCase (Prisma field names)
FIELD_MAP = {
    "business_name": "businessName",
    "zip_code": "zipCode",
    "industry_tags": "industryTags",
    "owner_name": "ownerName",
    "owner_title": "ownerTitle",
    "owner_email": "ownerEmail",
    "owner_phone": "ownerPhone",
    "owner_linkedin": "ownerLinkedin",
    "employee_count": "employeeCount",
    "annual_revenue_estimate": "annualRevenueEstimate",
    "year_established": "yearEstablished",
    "business_type": "businessType",
    "facebook_url": "facebookUrl",
    "instagram_url": "instagramUrl",
    "twitter_url": "twitterUrl",
    "linkedin_url": "linkedinUrl",
    "youtube_url": "youtubeUrl",
    "tiktok_url": "tiktokUrl",
    "tech_stack": "techStack",
    "has_website": "hasWebsite",
    "website_platform": "websitePlatform",
    "has_ssl": "hasSsl",
    "mobile_friendly": "mobileFriendly",
    "google_rating": "googleRating",
    "google_review_count": "googleReviewCount",
    "yelp_rating": "yelpRating",
    "yelp_review_count": "yelpReviewCount",
    "bbb_rating": "bbbRating",
    "bbb_accredited": "bbbAccredited",
    "runs_google_ads": "runsGoogleAds",
    "runs_facebook_ads": "runsFacebookAds",
    "has_google_business_profile": "hasGoogleBusinessProfile",
    "latitude": "latitude",
    "longitude": "longitude",
    "google_place_id": "googlePlaceId",
    "business_hours": "businessHours",
    "photo_count": "photoCount",
    "price_level": "priceLevel",
    "description": "description",
    "service_options": "serviceOptions",
    "email_verified": "emailVerified",
    "owner_email_verified": "ownerEmailVerified",
    "icp_score": "icpScore",
    "source_url": "sourceUrl",
    "scraped_at": "scrapedAt",
    "enriched_at": "enrichedAt",
    "last_enriched_at": "lastEnrichedAt",
    "updated_at": "updatedAt",
    "is_enriched": "isEnriched",
    "enrichment_errors": "enrichmentErrors",
    "quality_score": "qualityScore",
}

# Reverse map: camelCase -> snake_case
REVERSE_FIELD_MAP = {v: k for k, v in FIELD_MAP.items()}


def to_prisma_data(snake_dict: dict) -> dict:
    """Convert a snake_case dict (from scrapers) to camelCase dict (for Prisma)."""
    prisma_data = {}
    for key, value in snake_dict.items():
        if value is None:
            continue
        prisma_key = FIELD_MAP.get(key, key)
        # Prisma Json fields must be passed as a JSON-serializable value.
        # Convert dicts/lists to JSON strings to avoid GraphQL parse errors
        # with keys like "Google Analytics" that contain spaces.
        if prisma_key in _JSON_FIELDS and isinstance(value, (dict, list)):
            value = _json.dumps(value)
        prisma_data[prisma_key] = value
    return prisma_data


def to_snake_dict(prisma_obj) -> dict:
    """Convert a Prisma model instance to a snake_case dict."""
    result = {}
    obj_dict = prisma_obj.model_dump() if hasattr(prisma_obj, 'model_dump') else prisma_obj.dict()
    for key, value in obj_dict.items():
        snake_key = REVERSE_FIELD_MAP.get(key, key)
        result[snake_key] = value
    return result
