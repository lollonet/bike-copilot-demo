"""Optional Playwright-based fetcher for JS-heavy or login pages.

Usage is lazy-imported so projects without playwright installed keep working.
Install extra manually when needed:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

from typing import Optional


def fetch_rendered(
    url: str,
    wait_ms: int = 1500,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    user_selector: str = "#username",
    pass_selector: str = "#password",
    submit_selector: str = "button[type=submit]",
) -> str:
    """Fetch rendered HTML using Playwright Chromium.

    If login_url and credentials are provided, performs a simple form login first.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        if login_url and username and password:
            page.goto(login_url, wait_until="networkidle")
            page.fill(user_selector, username)
            page.fill(pass_selector, password)
            page.click(submit_selector)
            page.wait_for_timeout(wait_ms)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
        return html
