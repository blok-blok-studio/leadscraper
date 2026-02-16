"""Website tech stack analysis enrichment module."""

from __future__ import annotations

import logging
import re

from src.enrichment.base import BaseEnricher
from src.scrapers.http_client import ScraperHttpClient

logger = logging.getLogger(__name__)

# Common platform signatures found in HTML
PLATFORM_SIGNATURES = {
    "WordPress": [
        r'wp-content', r'wp-includes', r'wordpress',
        r'<meta name="generator" content="WordPress',
    ],
    "Shopify": [
        r'cdn\.shopify\.com', r'shopify\.com', r'Shopify\.theme',
    ],
    "Wix": [
        r'wix\.com', r'wixstatic\.com', r'X-Wix-',
    ],
    "Squarespace": [
        r'squarespace\.com', r'sqsp\.com', r'squarespace-cdn',
    ],
    "GoDaddy": [
        r'godaddy\.com', r'secureserver\.net', r'wsimg\.com',
    ],
    "Weebly": [
        r'weebly\.com', r'editmysite\.com',
    ],
    "Webflow": [
        r'webflow\.com', r'assets\.website-files\.com',
    ],
    "Joomla": [
        r'/media/jui/', r'<meta name="generator" content="Joomla',
    ],
    "Drupal": [
        r'drupal\.js', r'sites/default/files', r'Drupal\.settings',
    ],
}

# Common tech/tools signatures
TECH_SIGNATURES = {
    "Google Analytics": [r'google-analytics\.com', r'gtag', r'UA-\d+'],
    "Google Tag Manager": [r'googletagmanager\.com', r'GTM-'],
    "Facebook Pixel": [r'connect\.facebook\.net', r'fbq\('],
    "Hotjar": [r'hotjar\.com', r'hj\('],
    "Mailchimp": [r'mailchimp\.com', r'mc\.us\d+'],
    "HubSpot": [r'hubspot\.com', r'hs-scripts'],
    "Intercom": [r'intercom\.io', r'widget\.intercom\.io'],
    "Zendesk": [r'zendesk\.com', r'zdassets\.com'],
    "LiveChat": [r'livechatinc\.com', r'livechat'],
    "Calendly": [r'calendly\.com'],
    "Stripe": [r'stripe\.com', r'js\.stripe'],
    "PayPal": [r'paypal\.com', r'paypalobjects\.com'],
    "jQuery": [r'jquery[\.-]', r'jquery\.min\.js'],
    "React": [r'react\.production', r'__NEXT_DATA__', r'_next/'],
    "Vue.js": [r'vue\.js', r'vue\.min\.js', r'__vue__'],
    "Bootstrap": [r'bootstrap\.min', r'bootstrap\.css'],
    "Tailwind CSS": [r'tailwindcss', r'tailwind\.css'],
}


class TechStackEnricher(BaseEnricher):
    """Analyze a business website to detect its tech stack."""

    MODULE_NAME = "website_tech_stack"

    def __init__(self):
        self.http = ScraperHttpClient()

    def enrich(self, lead) -> dict:
        if not lead.website:
            return {}

        try:
            response = self.http.get(lead.website)
            html = response.text
            headers = dict(response.headers)
        except Exception as e:
            logger.debug(f"[TechStack] Could not fetch {lead.website}: {e}")
            return {}

        result = {}

        # Detect platform
        platform = self._detect_platform(html)
        if platform:
            result["website_platform"] = platform

        # Detect tech stack
        tech_stack = self._detect_tech(html, headers)
        if tech_stack:
            result["tech_stack"] = tech_stack

        # SSL check
        result["has_ssl"] = lead.website.startswith("https")

        # Mobile-friendly heuristic (viewport meta tag)
        result["mobile_friendly"] = bool(
            re.search(r'<meta[^>]*name=["\']viewport["\']', html, re.IGNORECASE)
        )

        # Detect ad indicators
        result["runs_google_ads"] = bool(
            re.search(r'googleads|adwords|gads|google_ads', html, re.IGNORECASE)
        )
        result["runs_facebook_ads"] = bool(
            re.search(r'facebook.*pixel|fbq\(|fb-pixel', html, re.IGNORECASE)
        )

        return result

    def _detect_platform(self, html: str) -> str | None:
        """Detect the website platform/CMS."""
        for platform, patterns in PLATFORM_SIGNATURES.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    return platform
        return None

    def _detect_tech(self, html: str, headers: dict) -> dict:
        """Detect technologies used on the website."""
        detected = {}
        for tech, patterns in TECH_SIGNATURES.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    detected[tech] = True
                    break

        # Check headers for additional tech
        server = headers.get("server", "").lower()
        if "nginx" in server:
            detected["Nginx"] = True
        elif "apache" in server:
            detected["Apache"] = True
        elif "cloudflare" in server:
            detected["Cloudflare"] = True

        powered_by = headers.get("x-powered-by", "").lower()
        if "php" in powered_by:
            detected["PHP"] = True
        elif "asp.net" in powered_by:
            detected["ASP.NET"] = True
        elif "express" in powered_by:
            detected["Express.js"] = True

        return detected

    def close(self):
        self.http.close()
