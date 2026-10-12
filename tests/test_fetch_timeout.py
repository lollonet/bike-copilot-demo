"""Test for SEC-004: Unbounded timeouts enable DoS (issue #48).

This test verifies that fetch_and_parse_urls respects max_total_seconds limit.
"""

from __future__ import annotations

from pathlib import Path
import time
import pytest

from app.adapters.web_adapter import fetch_and_parse_urls


def test_fetch_respects_total_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that fetch operation aborts when max_total_seconds is exceeded."""
    import httpx

    # Create test mapping
    mapping_path = tmp_path / "test_mapping.yaml"
    mapping_path.write_text(
        """
root: '.item'
brand: '.brand'
mpn: '.mpn'
name: '.name'
price: '.price'
supplier: test-supplier
pagination:
  next: 'a.next'
"""
    )

    # Mock client that simulates slow responses
    class SlowResponse:
        def __init__(self, html: str):
            self.text = html

        def raise_for_status(self) -> None:
            pass

    class SlowClient:
        call_count = 0  # Class variable for shared state

        def __init__(
            self,
            timeout: float,
            headers: dict[str, str],
            follow_redirects: bool,
            verify: bool,
        ):
            pass

        def get(self, url: str) -> SlowResponse:
            SlowClient.call_count += 1
            # Simulate slow response (0.5 seconds per page)
            time.sleep(0.5)
            # Always return a page with a "next" link
            html = f"""
            <html>
                <div class="item">
                    <span class="brand">Test</span>
                    <span class="mpn">ITEM-{SlowClient.call_count}</span>
                    <span class="name">Item {SlowClient.call_count}</span>
                    <span class="price">10,00 €</span>
                </div>
                <a class="next" href="https://example.com/page{SlowClient.call_count + 1}">Next</a>
            </html>
            """
            return SlowResponse(html)

        def __enter__(self) -> SlowClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

    monkeypatch.setattr(httpx, "Client", SlowClient, raising=False)

    start_time = time.time()

    # Try to fetch with max_total_seconds=2 (should abort after 2 seconds)
    # With 0.5s per page, we'd get at most 4 pages before timeout
    products, offers = fetch_and_parse_urls(
        urls=["https://example.com/page1"],
        mapping_yaml=mapping_path,
        follow_next=True,
        max_pages=100,  # Set high to ensure timeout is what stops us
        delay_sec=0.0,
        max_total_seconds=2.0,
    )

    elapsed_time = time.time() - start_time

    # Verify timeout was respected (should be ~2 seconds, allow some margin)
    assert elapsed_time < 3.0, f"Operation took {elapsed_time}s, expected < 3s"
    assert elapsed_time >= 1.5, f"Operation took {elapsed_time}s, expected >= 1.5s"

    # Verify we got some products but not all 100 pages
    assert len(products) > 0, "Should have fetched at least 1 product"
    assert len(products) < 100, (
        f"Should not have fetched all 100 pages (got {len(products)})"
    )


def test_fetch_without_timeout_completes_all_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that fetch without timeout completes all pages normally."""
    import httpx

    # Create test mapping
    mapping_path = tmp_path / "test_mapping.yaml"
    mapping_path.write_text(
        """
root: '.item'
brand: '.brand'
mpn: '.mpn'
name: '.name'
price: '.price'
supplier: test-supplier
pagination:
  next: 'a.next'
"""
    )

    # Mock client with limited pages
    class MockResponse:
        def __init__(self, html: str):
            self.text = html

        def raise_for_status(self) -> None:
            pass

    class MockClient:
        call_count = 0  # Class variable for shared state

        def __init__(
            self,
            timeout: float,
            headers: dict[str, str],
            follow_redirects: bool,
            verify: bool,
        ):
            pass

        def get(self, url: str) -> MockResponse:
            MockClient.call_count += 1
            # Return pages with "next" link for first 3 pages only
            if MockClient.call_count < 3:
                html = f"""
                <html>
                    <div class="item">
                        <span class="brand">Test</span>
                        <span class="mpn">ITEM-{MockClient.call_count}</span>
                        <span class="name">Item {MockClient.call_count}</span>
                        <span class="price">10,00 €</span>
                    </div>
                    <a class="next" href="https://example.com/page{MockClient.call_count + 1}">Next</a>
                </html>
                """
            else:
                # Last page, no "next" link
                html = f"""
                <html>
                    <div class="item">
                        <span class="brand">Test</span>
                        <span class="mpn">ITEM-{MockClient.call_count}</span>
                        <span class="name">Item {MockClient.call_count}</span>
                        <span class="price">10,00 €</span>
                    </div>
                </html>
                """
            return MockResponse(html)

        def __enter__(self) -> MockClient:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            pass

    monkeypatch.setattr(httpx, "Client", MockClient, raising=False)

    # Fetch without timeout (should complete all 3 pages)
    products, offers = fetch_and_parse_urls(
        urls=["https://example.com/page1"],
        mapping_yaml=mapping_path,
        follow_next=True,
        max_pages=10,
        delay_sec=0.0,
        max_total_seconds=None,  # No timeout
    )

    # Verify we got all 3 products
    assert len(products) == 3, f"Expected 3 products, got {len(products)}"
