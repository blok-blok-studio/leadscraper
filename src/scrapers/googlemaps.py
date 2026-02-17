"""Google Maps scraper — clicks into each listing detail page for full data extraction."""

from __future__ import annotations

import json
import logging
import re
import time
from urllib.parse import quote_plus, unquote

from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class GoogleMapsScraper(BaseScraper):
    """Scrape business listings from Google Maps with detail page extraction."""

    SOURCE_NAME = "googlemaps"
    BASE_URL = "https://www.google.com/maps/search"

    def search(self, category: str, location: str, max_pages: int = 5) -> list[dict]:
        """
        Search Google Maps for businesses and scrape each detail page.
        max_pages controls how many scroll batches to load (each ~7-10 results).
        """
        query = f"{category} in {location}"
        url = f"{self.BASE_URL}/{quote_plus(query)}"

        logger.info(f"[GoogleMaps] Searching: {query}")

        try:
            listing_urls = self._collect_listing_urls(url, scroll_count=max_pages)
            logger.info(f"[GoogleMaps] Found {len(listing_urls)} listing URLs")

            leads = []
            for i, listing_url in enumerate(listing_urls):
                try:
                    lead = self._scrape_detail_page(listing_url, category)
                    if lead:
                        leads.append(lead)
                        logger.debug(f"[GoogleMaps] [{i+1}/{len(listing_urls)}] {lead['business_name']}")
                    else:
                        logger.debug(f"[GoogleMaps] [{i+1}/{len(listing_urls)}] Skipped (closed/invalid)")
                except Exception as e:
                    logger.debug(f"[GoogleMaps] Detail page error: {e}")
                    continue

            logger.info(f"[GoogleMaps] Extracted {len(leads)} leads from detail pages")
            return leads
        except Exception as e:
            logger.error(f"[GoogleMaps] Search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────────────────
    # Step 1: Scroll search results to collect listing URLs
    # ──────────────────────────────────────────────────────────────────────

    def _collect_listing_urls(self, url: str, scroll_count: int = 5) -> list[str]:
        """Load Google Maps search results, scroll to load more, collect all listing URLs."""
        if self.http._browser_client is None:
            from src.scrapers.http_client import BrowserClient
            self.http._browser_client = BrowserClient()

        bc = self.http._browser_client
        bc._ready.wait(timeout=30)

        def _do_scroll(url, scroll_count):
            page = bc._context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                # Accept Google consent if it appears
                try:
                    consent_btn = page.query_selector(
                        'button:has-text("Accept all"), '
                        'button:has-text("Reject all"), '
                        'form[action*="consent"] button'
                    )
                    if consent_btn:
                        consent_btn.click()
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

                # Find the scrollable results panel
                feed_selector = 'div[role="feed"]'
                try:
                    page.wait_for_selector(feed_selector, timeout=10000)
                except Exception:
                    logger.debug("[GoogleMaps] Could not find results feed")
                    return []

                # Scroll to load more results
                for i in range(scroll_count):
                    page.evaluate(f"""
                        const feed = document.querySelector('{feed_selector}');
                        if (feed) {{ feed.scrollTop = feed.scrollHeight; }}
                    """)
                    page.wait_for_timeout(2000)

                    end_marker = page.query_selector(
                        'p.fontBodyMedium span:has-text("end of list"), '
                        'span:has-text("You\'ve reached the end")'
                    )
                    if end_marker:
                        logger.debug(f"[GoogleMaps] End of results at scroll {i+1}")
                        break

                # Collect all listing URLs
                links = page.query_selector_all('a[href*="/maps/place/"]')
                urls = []
                seen = set()
                for link in links:
                    href = link.get_attribute("href")
                    if href and href not in seen:
                        seen.add(href)
                        urls.append(href)

                return urls
            except Exception as e:
                logger.error(f"[GoogleMaps] Scroll error: {e}")
                return []
            finally:
                page.close()

        future = bc._executor.submit(_do_scroll, url, scroll_count)
        return future.result(timeout=120)

    # ──────────────────────────────────────────────────────────────────────
    # Step 2: Scrape each listing's detail page
    # ──────────────────────────────────────────────────────────────────────

    def _scrape_detail_page(self, url: str, search_category: str) -> dict | None:
        """Navigate to a Google Maps listing detail page and extract all available data."""
        bc = self.http._browser_client
        bc._ready.wait(timeout=30)

        def _do_scrape(url):
            page = bc._context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                # ── Check for permanently/temporarily closed ──
                page_text = page.inner_text("body")
                if "Permanently closed" in page_text or "Temporarily closed" in page_text:
                    logger.debug(f"[GoogleMaps] Skipping closed business")
                    return None

                # ── Business name ──
                name = ""
                name_el = page.query_selector("h1")
                if name_el:
                    name = name_el.inner_text().strip()
                if not name or len(name) < 2:
                    return None

                # ── Category (real category from Google, not search term) ──
                category = search_category
                cat_el = page.query_selector('button[jsaction*="category"]')
                if cat_el:
                    cat_text = cat_el.inner_text().strip()
                    if cat_text and len(cat_text) > 1:
                        category = cat_text

                # ── Rating and review count ──
                rating = None
                review_count = None

                rating_el = page.query_selector('div.fontDisplayLarge')
                if rating_el:
                    try:
                        rating = float(rating_el.inner_text().strip())
                    except ValueError:
                        pass

                # Try aria-label on the stars element
                if not rating:
                    stars_el = page.query_selector('span[role="img"][aria-label*="star"]')
                    if stars_el:
                        label = stars_el.get_attribute("aria-label") or ""
                        m = re.search(r"(\d+\.?\d?)\s*star", label)
                        if m:
                            rating = float(m.group(1))

                # Review count — look for text like "(1,234)" or "1,234 reviews"
                review_els = page.query_selector_all('span')
                for el in review_els:
                    try:
                        txt = el.inner_text().strip()
                        m = re.match(r"^\(?(\d[\d,]*)\)?\s*(reviews?)?$", txt, re.I)
                        if m and rating:
                            review_count = int(m.group(1).replace(",", ""))
                            break
                    except Exception:
                        continue

                # ── Phone ──
                phone = None
                phone_el = page.query_selector('button[data-item-id*="phone"]')
                if phone_el:
                    label = phone_el.get_attribute("aria-label") or ""
                    # aria-label is like "Phone: (305) 555-1234"
                    pm = re.search(r'\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}', label)
                    if pm:
                        phone = pm.group(0)

                # ── Address ──
                address = ""
                city = ""
                state = ""
                zip_code = ""

                addr_el = page.query_selector('button[data-item-id="address"]')
                if addr_el:
                    addr_text = addr_el.get_attribute("aria-label") or ""
                    # Remove "Address: " prefix
                    addr_text = re.sub(r"^Address:\s*", "", addr_text).strip()
                    # Parse "123 Main St, City, ST 12345"
                    addr_match = re.match(
                        r"(.+?),\s*([A-Za-z\s]+),\s*([A-Z]{2})\s*(\d{5})?",
                        addr_text
                    )
                    if addr_match:
                        address = addr_match.group(1).strip()
                        city = addr_match.group(2).strip()
                        state = addr_match.group(3).strip()
                        zip_code = (addr_match.group(4) or "").strip()
                    else:
                        # Fallback: store full address text
                        address = addr_text

                # ── Website ──
                website = None
                web_el = page.query_selector('a[data-item-id="authority"]')
                if web_el:
                    href = web_el.get_attribute("href") or ""
                    if href and "google.com" not in href:
                        website = href

                # ── Business hours ──
                hours = {}
                hours_rows = page.query_selector_all('table.eK4R0e tr, table tr')
                for row in hours_rows:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        try:
                            day = cells[0].inner_text().strip()
                            time_text = cells[1].inner_text().strip()
                            if day and time_text:
                                hours[day] = time_text
                        except Exception:
                            continue

                # Fallback: try aria-label on hours button
                if not hours:
                    hours_btn = page.query_selector('button[data-item-id*="hour"], div[aria-label*="Sunday"]')
                    if hours_btn:
                        label = hours_btn.get_attribute("aria-label") or ""
                        if label:
                            hours = {"summary": label}

                # ── Coordinates from URL ──
                latitude = None
                longitude = None
                current_url = page.url
                coord_match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", current_url)
                if coord_match:
                    latitude = float(coord_match.group(1))
                    longitude = float(coord_match.group(2))

                # ── Place ID from URL ──
                place_id = None
                pid_match = re.search(r"!1s(0x[a-f0-9]+:0x[a-f0-9]+)", current_url)
                if pid_match:
                    place_id = pid_match.group(1)
                # Also try extracting from ChIJ format
                if not place_id:
                    pid_match2 = re.search(r"!1s(ChIJ[\w\-]+)", current_url)
                    if pid_match2:
                        place_id = pid_match2.group(1)

                # ── Photos count ──
                photo_count = None
                photo_el = page.query_selector('button[aria-label*="photo"]')
                if photo_el:
                    label = photo_el.get_attribute("aria-label") or ""
                    pm = re.search(r"(\d[\d,]*)\s*photo", label, re.I)
                    if pm:
                        photo_count = int(pm.group(1).replace(",", ""))

                # ── Price level ──
                price_level = None
                price_el = page.query_selector('span[aria-label*="Price"], span:has-text("$")')
                if price_el:
                    price_text = price_el.inner_text().strip()
                    if re.match(r"^\$+$", price_text):
                        price_level = price_text

                # ── Description / About ──
                description = None
                about_el = page.query_selector('div.PYvSYb, div[class*="fontBody"] p')
                if about_el:
                    desc = about_el.inner_text().strip()
                    if desc and len(desc) > 10:
                        description = desc[:1000]  # Cap at 1000 chars

                # ── Service options (Dine-in, Delivery, Takeout, etc.) ──
                service_options = {}
                option_els = page.query_selector_all('div[aria-label*="offers"] span, div[class*="LTs0Rc"]')
                for opt_el in option_els:
                    try:
                        opt = opt_el.inner_text().strip()
                        if opt and len(opt) < 50:
                            service_options[opt] = True
                    except Exception:
                        continue

                # Also try the structured chips
                if not service_options:
                    chip_els = page.query_selector_all('div[role="img"][aria-label]')
                    for chip in chip_els:
                        try:
                            label = chip.get_attribute("aria-label") or ""
                            if any(kw in label.lower() for kw in ["dine-in", "delivery", "takeout", "curbside", "drive-through"]):
                                service_options[label] = True
                        except Exception:
                            continue

                return {
                    "business_name": name,
                    "phone": phone,
                    "address": address,
                    "city": city,
                    "state": state,
                    "zip_code": zip_code,
                    "website": website,
                    "category": category,
                    "source_url": current_url,
                    "google_rating": rating,
                    "google_review_count": review_count,
                    "has_google_business_profile": True,
                    "latitude": latitude,
                    "longitude": longitude,
                    "google_place_id": place_id,
                    "business_hours": hours if hours else None,
                    "photo_count": photo_count,
                    "price_level": price_level,
                    "description": description,
                    "service_options": service_options if service_options else None,
                }

            except Exception as e:
                logger.error(f"[GoogleMaps] Detail scrape error: {e}")
                return None
            finally:
                page.close()

        future = bc._executor.submit(_do_scrape, url)
        result = future.result(timeout=60)

        # Rate limit between detail pages
        time.sleep(2)
        return result
