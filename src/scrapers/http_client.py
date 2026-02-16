"""HTTP client with retry logic, rate limiting, and rotating user agents."""

from __future__ import annotations

import time
import random
import logging

import httpx
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import REQUEST_TIMEOUT, MAX_RETRIES, PROXY_URL, REQUEST_DELAY

logger = logging.getLogger(__name__)

_ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")


class ScraperHttpClient:
    """HTTP client configured for web scraping with protections."""

    def __init__(self):
        self._last_request_time = 0
        proxies = PROXY_URL if PROXY_URL else None
        self.client = httpx.Client(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            proxy=proxies,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def _get_headers(self) -> dict:
        """Generate realistic browser headers."""
        return {
            "User-Agent": _ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _rate_limit(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            jitter = random.uniform(0, REQUEST_DELAY * 0.5)
            time.sleep(REQUEST_DELAY - elapsed + jitter)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying request (attempt {retry_state.attempt_number})"
        ),
    )
    def get(self, url: str, params: dict = None) -> httpx.Response:
        """Make a GET request with rate limiting and retries."""
        self._rate_limit()
        headers = self._get_headers()
        logger.debug(f"GET {url}")
        response = self.client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response

    def get_soup(self, url: str, params: dict = None):
        """Make a GET request and return a BeautifulSoup object."""
        from bs4 import BeautifulSoup

        response = self.get(url, params=params)
        return BeautifulSoup(response.text, "lxml")

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
