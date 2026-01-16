"""Integration tests for B2B dealer data extraction using Playwright.

These tests require:
1. Playwright installed: uv add --dev playwright && playwright install chromium
2. Valid dealer credentials in environment variables

Run with: pytest tests/test_b2b_integration.py -v --run-integration
Skip by default in normal test runs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from app.types import ProductCandidate, OfferCandidate

# Check if playwright is available
try:
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def has_dealer_credentials(dealer_key: str) -> bool:
    """Check if credentials are available for a dealer."""
    username_env = f"DEALER_{dealer_key.upper()}_USERNAME"
    password_env = f"DEALER_{dealer_key.upper()}_PASSWORD"
    return bool(os.getenv(username_env) and os.getenv(password_env))


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


class TestCicloPromoIntegration:
    """Integration tests for CicloPromo B2B extraction."""

    DEALER_KEY = "ciclopromo"
    LOGIN_URL = "https://shop.ciclopromo.com/it/accesso/invia"
    PREFLIGHT_URL = "https://shop.ciclopromo.com/it/home"
    TEST_URL = "https://shop.ciclopromo.com/it/shop?brands=SHIMANO%7C"
    MAPPING_PATH = Path("providers/web-ciclopromo.yaml")

    @pytest.mark.skipif(
        not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"
    )
    @pytest.mark.skipif(
        not has_dealer_credentials("ciclopromo"),
        reason="CicloPromo credentials not configured",
    )
    def test_ciclopromo_extraction(self, playwright_browser) -> None:
        """Test extraction from CicloPromo with real credentials."""
        from app.adapters.web_adapter import parse_html, _load_mapping

        username = os.environ["DEALER_CICLOPROMO_USERNAME"]
        password = os.environ["DEALER_CICLOPROMO_PASSWORD"]

        page = playwright_browser.new_page()

        # Navigate to preflight URL first (sets cookies)
        page.goto(self.PREFLIGHT_URL, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Perform login
        page.goto("https://shop.ciclopromo.com/it/accesso", wait_until="networkidle")
        page.fill('input[name="email"]', username)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        # Navigate to product listing
        page.goto(self.TEST_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        html = page.content()
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
        not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"
    )
    @pytest.mark.skipif(
        not has_dealer_credentials("ciclodiffusione"),
        reason="Ciclodiffusione credentials not configured",
    )
    def test_ciclodiffusione_extraction(self, playwright_browser) -> None:
        """Test extraction from Ciclodiffusione with real credentials."""
        from app.adapters.web_adapter import parse_html, _load_mapping

        username = os.environ["DEALER_CICLODIFFUSIONE_USERNAME"]
        password = os.environ["DEALER_CICLODIFFUSIONE_PASSWORD"]

        page = playwright_browser.new_page()

        # Navigate to login page
        page.goto(self.PREFLIGHT_URL, wait_until="networkidle")
        page.wait_for_timeout(1000)

        # Perform login
        page.fill('input[name="credential_id"]', username)
        page.fill('input[name="credential_password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3000)

        # Navigate to product listing
        page.goto(self.TEST_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        html = page.content()
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
        not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"
    )
    @pytest.mark.skipif(
        not has_dealer_credentials("rms"),
        reason="RMS credentials not configured",
    )
    def test_rms_extraction(self, playwright_browser) -> None:
        """Test extraction from RMS SPA with real credentials."""
        from app.adapters.web_adapter import parse_html, _load_mapping

        username = os.environ["DEALER_RMS_USERNAME"]
        password = os.environ["DEALER_RMS_PASSWORD"]

        page = playwright_browser.new_page()

        # Navigate to login page
        page.goto(self.PREFLIGHT_URL, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # RMS uses Angular - wait for form to render
        page.wait_for_selector('input[type="text"]', timeout=10000)
        page.fill('input[type="text"]', username)
        page.fill('input[type="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)  # SPA needs more time

        # Navigate to product listing
        page.goto(self.TEST_URL, wait_until="networkidle")
        page.wait_for_timeout(5000)  # Wait for Angular to render products

        # Wait for product cards to appear
        try:
            page.wait_for_selector(".product-card", timeout=10000)
        except Exception:
            # Take screenshot for debugging
            page.screenshot(path="out/rms-debug.png")
            pytest.fail("Product cards did not appear - check out/rms-debug.png")

        html = page.content()
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

    @pytest.mark.skipif(
        not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"
    )
    def test_ciclopromo_homepage_accessible(self, playwright_browser) -> None:
        """Verify CicloPromo homepage is accessible."""
        page = playwright_browser.new_page()
        response = page.goto(
            "https://shop.ciclopromo.com/it/home", wait_until="domcontentloaded"
        )
        assert response is not None
        assert response.status == 200
        page.close()

    @pytest.mark.skipif(
        not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"
    )
    def test_ciclodiffusione_homepage_accessible(self, playwright_browser) -> None:
        """Verify Ciclodiffusione homepage is accessible."""
        page = playwright_browser.new_page()
        response = page.goto(
            "https://www.ciclodiffusione.com", wait_until="domcontentloaded"
        )
        assert response is not None
        assert response.status == 200
        page.close()

    @pytest.mark.skipif(
        not PLAYWRIGHT_AVAILABLE, reason="Playwright not installed"
    )
    def test_rms_homepage_accessible(self, playwright_browser) -> None:
        """Verify RMS homepage is accessible."""
        page = playwright_browser.new_page()
        response = page.goto(
            "https://b2bnew.rms.it/ciclo/it/login", wait_until="domcontentloaded"
        )
        assert response is not None
        assert response.status == 200
        page.close()
