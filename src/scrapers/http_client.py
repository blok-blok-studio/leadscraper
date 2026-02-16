"""HTTP client with retry logic, rate limiting, rotating user agents, and Playwright browser rendering."""

from __future__ import annotations

import time
import random
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future

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
        self._browser_client: BrowserClient | None = None

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

    def get_rendered_soup(self, url: str, params: dict = None, wait_selector: str = None, wait_ms: int = 3000):
        """
        Fetch a page using headless Chromium (Playwright) for full JS rendering.
        Runs Playwright in a separate thread to avoid asyncio event loop conflicts.

        Args:
            url: The URL to fetch.
            params: Optional query parameters (will be appended to URL).
            wait_selector: Optional CSS selector to wait for before extracting HTML.
            wait_ms: Extra milliseconds to wait after page load (default 3000).

        Returns:
            BeautifulSoup object of the fully-rendered page.
        """
        from bs4 import BeautifulSoup

        self._rate_limit()

        # Build full URL with params
        if params:
            from urllib.parse import urlencode
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"

        # Lazy-init the browser client
        if self._browser_client is None:
            self._browser_client = BrowserClient()

        logger.debug(f"GET (Playwright) {url}")
        html = self._browser_client.fetch(url, wait_selector=wait_selector, wait_ms=wait_ms)
        return BeautifulSoup(html, "lxml")

    def close(self):
        """Close the HTTP client and browser."""
        self.client.close()
        if self._browser_client is not None:
            self._browser_client.close()
            self._browser_client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class BrowserClient:
    """
    Headless Chromium browser client using Playwright for JS-rendered pages.

    Runs Playwright's sync API in a dedicated background thread to avoid
    conflicts with asyncio event loops (the CLI uses asyncio.run()).
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
        # Initialize Playwright in the background thread
        self._ready = threading.Event()
        self._pw = None
        self._browser = None
        self._context = None
        self._init_future = self._executor.submit(self._init_browser)
        self._init_future.result(timeout=30)  # Wait for browser init

    def _init_browser(self):
        """Initialize Playwright browser (runs in background thread)."""
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=_ua.random,
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
            bypass_csp=True,
        )
        # Stealth patches to avoid bot detection
        self._context.add_init_script("""
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            // Override chrome automation property
            window.chrome = { runtime: {} };
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
            // Override plugins length
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            // Override languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)
        self._ready.set()
        logger.info("Playwright browser initialized (headless Chromium)")

    def _fetch_in_thread(self, url: str, wait_selector: str = None, wait_ms: int = 3000) -> str:
        """Actual fetch logic — runs inside the Playwright thread."""
        self._ready.wait(timeout=30)
        page = self._context.new_page()
        try:
            # Block unnecessary resources to speed up loading
            page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
            page.route("**/analytics*", lambda route: route.abort())
            page.route("**/tracking*", lambda route: route.abort())
            page.route("**/ads*", lambda route: route.abort())

            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for specific selector or a general wait
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.debug(f"Selector '{wait_selector}' not found, continuing anyway")

            # Additional wait for dynamic JS content to render
            page.wait_for_timeout(wait_ms)

            # Scroll down to trigger lazy-loaded content
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(1000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)

            html = page.content()
            logger.debug(f"Playwright rendered {len(html)} bytes from {url}")
            return html
        except Exception as e:
            logger.error(f"Playwright fetch error for {url}: {e}")
            raise
        finally:
            page.close()

    def fetch(self, url: str, wait_selector: str = None, wait_ms: int = 3000) -> str:
        """
        Navigate to a URL and return the fully rendered HTML.
        Submits work to the Playwright thread and waits for the result.

        Args:
            url: Full URL to navigate to.
            wait_selector: Optional CSS selector to wait for.
            wait_ms: Extra wait time in ms after load.

        Returns:
            Rendered HTML string.
        """
        future = self._executor.submit(self._fetch_in_thread, url, wait_selector, wait_ms)
        return future.result(timeout=60)

    def _close_in_thread(self):
        """Close browser resources (runs in Playwright thread)."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
            logger.info("Playwright browser closed")
        except Exception as e:
            logger.debug(f"Error closing Playwright: {e}")

    def close(self):
        """Shut down the browser and Playwright thread."""
        try:
            future = self._executor.submit(self._close_in_thread)
            future.result(timeout=10)
        except Exception as e:
            logger.debug(f"Error during Playwright shutdown: {e}")
        finally:
            self._executor.shutdown(wait=False)
