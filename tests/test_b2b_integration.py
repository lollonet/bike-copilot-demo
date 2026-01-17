"""Integration tests for B2B dealer data extraction using Playwright.

These tests require:
1. Playwright installed: uv sync --extra integration && playwright install chromium
2. Valid dealer credentials in environment variables

Run with: pytest --run-integration tests/test_b2b_integration.py -v
Skip by default in normal test runs.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

# Check if playwright is available
try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def has_dealer_credentials(dealer_key: str) -> bool:
    """Check if credentials are available for a dealer."""
    username_env = f"DEALER_{dealer_key.upper()}_USERNAME"
    password_env = f"DEALER_{dealer_key.upper()}_PASSWORD"
    username = os.getenv(username_env)
    password = os.getenv(password_env)
    return bool(username and password)


# Marker for integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def playwright_browser():
    """Provide a Playwright browser instance."""
    if not PLAYWRIGHT_AVAILABLE:
        pytest.skip("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def browser_context(playwright_browser):
    """Provide isolated browser context per test."""
    context = playwright_browser.new_context()
    yield context
    context.close()


class TestCicloPromoIntegration:
    """Integration tests for CicloPromo B2B extraction."""

    DEALER_KEY = "ciclopromo"
    LOGIN_URL = "https://shop.ciclopromo.com/it/accesso/invia"
    PREFLIGHT_URL = "https://shop.ciclopromo.com/it/home"
    TEST_URL = "https://shop.ciclopromo.com/it/shop?brands=SHIMANO%7C"
    MAPPING_PATH = Path("providers/web-ciclopromo.yaml")

    @pytest.mark.skipif(
        not has_dealer_credentials("ciclopromo"),
        reason="CicloPromo credentials not configured",
    )
    def test_ciclopromo_extraction(self, browser_context) -> None:
        """Test extraction from CicloPromo with real credentials."""
        from app.adapters.web_adapter import _load_mapping, parse_html

        username = os.getenv("DEALER_CICLOPROMO_USERNAME")
        password = os.getenv("DEALER_CICLOPROMO_PASSWORD")

        if not username or not password:
            pytest.skip("Missing CicloPromo credentials")

        page = browser_context.new_page()

        try:
            # Navigate to preflight URL first (sets cookies)
            response = page.goto(self.PREFLIGHT_URL, wait_until="networkidle", timeout=30000)
            if response and response.status >= 400:
                pytest.skip(f"HTTP {response.status} from {self.PREFLIGHT_URL}")

            # Perform login
            page.goto("https://shop.ciclopromo.com/it/accesso", wait_until="networkidle", timeout=30000)
            page.fill('input[name="email"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')

            # Wait for navigation after login
            page.wait_for_load_state("networkidle", timeout=10000)

            # Navigate to product listing
            response = page.goto(self.TEST_URL, wait_until="networkidle", timeout=30000)
            if response and response.status >= 400:
                pytest.skip(f"HTTP {response.status} from {self.TEST_URL}")

            html = page.content()

        except PlaywrightTimeoutError as e:
            pytest.skip(f"Network timeout accessing {self.DEALER_KEY}: {e}")
        finally:
            page.close()

        # Parse with mapping
        mapping = _load_mapping(self.MAPPING_PATH)
        products, offers = parse_html(html, mapping)

        # Assertions
        assert len(products) > 0, "No products extracted from CicloPromo"
        assert len(offers) > 0, "No offers extracted from CicloPromo"
        assert all(
            o.supplier == "CicloPromo" for o in offers
        ), "Supplier mismatch"

        # Validate data quality
        for product in products[:5]:
            assert product.name, f"Product missing name: {product}"
            assert product.mpn or product.brand, f"Product missing mpn/brand: {product}"

        for offer in offers[:5]:
            assert offer.price is not None and offer.price > 0, f"Invalid price: {offer}"


class TestCiclodiffusioneIntegration:
    """Integration tests for Ciclodiffusione B2B extraction."""

    DEALER_KEY = "ciclodiffusione"
    LOGIN_URL = "https://www.ciclodiffusione.com/restserver/login"
    PREFLIGHT_URL = "https://www.ciclodiffusione.com/login"
    TEST_URL = "https://www.ciclodiffusione.com/shop/complex/category/-/brand/-/?&sort-order-field=title&sort-order-type=1&product-page=90&page=1"
    MAPPING_PATH = Path("providers/web-ciclodiffusione.yaml")

    @pytest.mark.skipif(
        not has_dealer_credentials("ciclodiffusione"),
        reason="Ciclodiffusione credentials not configured",
    )
    def test_ciclodiffusione_extraction(self, browser_context) -> None:
        """Test extraction from Ciclodiffusione with real credentials."""
        from app.adapters.web_adapter import _load_mapping, parse_html

        username = os.getenv("DEALER_CICLODIFFUSIONE_USERNAME")
        password = os.getenv("DEALER_CICLODIFFUSIONE_PASSWORD")

        if not username or not password:
            pytest.skip("Missing Ciclodiffusione credentials")

        page = browser_context.new_page()

        try:
            # Navigate to login page
            response = page.goto(self.PREFLIGHT_URL, wait_until="networkidle", timeout=30000)
            if response and response.status >= 400:
                pytest.skip(f"HTTP {response.status} from {self.PREFLIGHT_URL}")

            # Perform login
            page.fill('input[name="credential_id"]', username)
            page.fill('input[name="credential_password"]', password)
            page.click('button[type="submit"]')

            # Wait for navigation after login
            page.wait_for_load_state("networkidle", timeout=10000)

            # Navigate to product listing
            response = page.goto(self.TEST_URL, wait_until="networkidle", timeout=30000)
            if response and response.status >= 400:
                pytest.skip(f"HTTP {response.status} from {self.TEST_URL}")

            html = page.content()

        except PlaywrightTimeoutError as e:
            pytest.skip(f"Network timeout accessing {self.DEALER_KEY}: {e}")
        finally:
            page.close()

        # Parse with mapping
        mapping = _load_mapping(self.MAPPING_PATH)
        products, offers = parse_html(html, mapping)

        # Assertions
        assert len(products) > 0, "No products extracted from Ciclodiffusione"
        assert len(offers) > 0, "No offers extracted from Ciclodiffusione"
        assert all(
            o.supplier == "Ciclodiffusione" for o in offers
        ), "Supplier mismatch"


class TestRMSIntegration:
    """Integration tests for RMS B2B extraction (SPA)."""

    DEALER_KEY = "rms"
    LOGIN_URL = "https://b2bnew.rms.it/api/auth/login"
    PREFLIGHT_URL = "https://b2bnew.rms.it/ciclo/it/login"
    TEST_URL = "https://b2bnew.rms.it/ciclo/it/category-list/B110/Kmc"
    MAPPING_PATH = Path("providers/web-rms.yaml")

    @pytest.mark.skipif(
        not has_dealer_credentials("rms"),
        reason="RMS credentials not configured",
    )
    def test_rms_extraction(self, browser_context) -> None:
        """Test extraction from RMS SPA with real credentials."""
        from app.adapters.web_adapter import _load_mapping, parse_html

        username = os.getenv("DEALER_RMS_USERNAME")
        password = os.getenv("DEALER_RMS_PASSWORD")

        if not username or not password:
            pytest.skip("Missing RMS credentials")

        page = browser_context.new_page()

        try:
            # Navigate to login page
            response = page.goto(self.PREFLIGHT_URL, wait_until="networkidle", timeout=30000)
            if response and response.status >= 400:
                pytest.skip(f"HTTP {response.status} from {self.PREFLIGHT_URL}")

            # RMS uses Angular - wait for form to render
            page.wait_for_selector('input[type="text"]', timeout=10000)
            page.fill('input[type="text"]', username)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"]')

            # Wait for navigation after login
            page.wait_for_load_state("networkidle", timeout=15000)

            # Navigate to product listing
            response = page.goto(self.TEST_URL, wait_until="networkidle", timeout=30000)
            if response and response.status >= 400:
                pytest.skip(f"HTTP {response.status} from {self.TEST_URL}")

            # Wait for product cards to appear (SPA needs time to render)
            try:
                page.wait_for_selector(".product-card", timeout=15000)
            except PlaywrightTimeoutError:
                # Take screenshot for debugging
                screenshot_dir = Path("out/test-screenshots")
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = screenshot_dir / f"rms-debug-{int(time.time())}.png"
                page.screenshot(path=str(screenshot_path))
                pytest.fail(f"Product cards did not appear - check {screenshot_path}")

            html = page.content()

        except PlaywrightTimeoutError as e:
            pytest.skip(f"Network timeout accessing {self.DEALER_KEY}: {e}")
        finally:
            page.close()

        # Parse with mapping
        mapping = _load_mapping(self.MAPPING_PATH)
        products, offers = parse_html(html, mapping)

        # Assertions
        assert len(products) > 0, "No products extracted from RMS"
        assert len(offers) > 0, "No offers extracted from RMS"
        assert all(o.supplier == "RMS" for o in offers), "Supplier mismatch"


# Smoke test that runs without credentials (tests page accessibility)
class TestDealerAccessibility:
    """Smoke tests for dealer page accessibility (no login required)."""

    def test_ciclopromo_homepage_accessible(self, browser_context) -> None:
        """Verify CicloPromo homepage is accessible."""
        page = browser_context.new_page()
        try:
            response = page.goto(
                "https://shop.ciclopromo.com/it/home", wait_until="domcontentloaded", timeout=30000
            )
            assert response is not None
            assert response.status == 200
        except PlaywrightTimeoutError:
            pytest.skip("CicloPromo homepage not accessible")
        finally:
            page.close()

    def test_ciclodiffusione_homepage_accessible(self, browser_context) -> None:
        """Verify Ciclodiffusione homepage is accessible."""
        page = browser_context.new_page()
        try:
            response = page.goto(
                "https://www.ciclodiffusione.com", wait_until="domcontentloaded", timeout=30000
            )
            assert response is not None
            assert response.status == 200
        except PlaywrightTimeoutError:
            pytest.skip("Ciclodiffusione homepage not accessible")
        finally:
            page.close()

    def test_rms_homepage_accessible(self, browser_context) -> None:
        """Verify RMS homepage is accessible."""
        page = browser_context.new_page()
        try:
            response = page.goto(
                "https://b2bnew.rms.it/ciclo/it/login", wait_until="domcontentloaded", timeout=30000
            )
            assert response is not None
            assert response.status == 200
        except PlaywrightTimeoutError:
            pytest.skip("RMS homepage not accessible")
        finally:
            page.close()
