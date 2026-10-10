"""
Playwright-based base scraper with JavaScript rendering,
auto-scroll, retry logic, and user-agent rotation.
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Page, BrowserContext


# Rotating user agents to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


# Common headers to look like a real browser
COMMON_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="120", "Not A(Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


class PlaywrightBaseScraper(ABC):
    """
    Base scraper using Playwright for JavaScript-rendered pages.

    Features:
    - Headless Chromium with real browser fingerprint
    - Auto-scroll to trigger lazy loading
    - Random delays between requests
    - Retry with exponential backoff
    - User-agent rotation
    - Raw HTML backup to disk
    - Stealth mode to avoid detection
    """

    SOURCE: str = ""
    BASE_URL: str = ""

    def __init__(
        self,
        headless: bool = True,
        min_delay: float = 5.0,
        max_delay: float = 12.0,
        max_retries: int = 3,
        html_backup_dir: str = "data/raw_html",
        stealth: bool = True,
    ):
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.html_backup_dir = Path(html_backup_dir)
        self.html_backup_dir.mkdir(parents=True, exist_ok=True)
        self.stealth = stealth

    @abstractmethod
    async def fetch_listings(
        self,
        city: str,
        locality: str | None = None,
        bhk: int = 2,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch listings from the source. Must be implemented by subclasses."""
        raise NotImplementedError

    async def _create_context(
        self,
        playwright: Any,
    ) -> tuple[Any, BrowserContext]:
        """Create a browser context with stealth settings."""
        user_agent = random.choice(USER_AGENTS)

        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            extra_http_headers=COMMON_HEADERS,
        )

        # Apply stealth scripts
        if self.stealth:
            await context.add_init_script(
                """
                // Remove webdriver flag
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );

                // Override hardware concurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });

                // Override device memory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                """
            )

        return browser, context

    async def _scroll_page(self, page: Page) -> None:
        """Scroll to bottom of page to trigger lazy loading."""
        try:
            # Get initial height
            height = await page.evaluate("document.body.scrollHeight")

            # Scroll in steps with random pauses
            for i in range(5):
                await page.evaluate(
                    f"window.scrollTo(0, {(i + 1) * height / 5})"
                )
                await asyncio.sleep(random.uniform(1.0, 2.5))

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.5, 1.0))

        except Exception:
            pass  # Non-critical

    async def _fetch_page(
        self,
        page: Page,
        url: str,
        wait_for_selector: str | None = None,
    ) -> str:
        """
        Fetch a page with retry logic and random delays.

        Returns the page HTML content.
        """
        for attempt in range(self.max_retries):
            try:
                # Random delay before request (longer to avoid detection)
                delay = random.uniform(self.min_delay, self.max_delay)
                await asyncio.sleep(delay)

                # Navigate
                await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=45000,
                )

                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(
                            wait_for_selector,
                            timeout=15000,
                        )
                    except Exception:
                        pass  # Continue even if selector not found

                # Scroll to trigger lazy loading
                await self._scroll_page(page)

                # Get HTML
                html = await page.content()

                # Check if we got blocked
                if self._is_blocked(html):
                    raise Exception("Access denied or blocked by website")

                # Save raw HTML backup
                self._save_html_backup(url, html)

                return html

            except Exception as exc:
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 10 + random.uniform(0, 10)
                    print(f"  Retry {attempt + 1}/{self.max_retries} for {url}: {exc}")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"  Failed after {self.max_retries} attempts: {url}")
                    raise

        return ""

    def _is_blocked(self, html: str) -> bool:
        """Check if the page indicates we've been blocked."""
        blocked_indicators = [
            "Access Denied",
            "Request Blocked",
            "Security Alert",
            "captcha",
            "robot",
            "bot detected",
            "suspicious activity",
            "blocked",
        ]
        html_lower = html.lower()
        return any(indicator.lower() in html_lower for indicator in blocked_indicators)

    def _save_html_backup(self, url: str, html: str) -> None:
        """Save raw HTML to disk for later re-parsing."""
        import hashlib
        from datetime import datetime

        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.SOURCE}_{timestamp}_{url_hash}.html"
        filepath = self.html_backup_dir / filename

        try:
            filepath.write_text(html, encoding="utf-8")
        except Exception:
            pass  # Non-critical

    async def _random_delay(self) -> None:
        """Wait a random amount of time between requests."""
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)
