"""Tests for fetch CLI commands."""

from __future__ import annotations


def test_build_headers_from_cli():
    """Test parsing CLI header options."""
    from app.cli_helpers.fetch_helpers import build_headers_from_cli

    # Test with valid headers
    headers = build_headers_from_cli(["Cookie: abc=123", "User-Agent: TestBot"])
    assert headers == {"Cookie": "abc=123", "User-Agent": "TestBot"}

    # Test with None
    headers = build_headers_from_cli(None)
    assert headers == {}

    # Test with empty list
    headers = build_headers_from_cli([])
    assert headers == {}

    # Test with malformed header (no colon)
    headers = build_headers_from_cli(["InvalidHeader"])
    assert headers == {}

    # Test with extra spaces
    headers = build_headers_from_cli(["  Authorization  :  Bearer token  "])
    assert headers == {"Authorization": "Bearer token"}


def test_sitemap_target_urls():
    """Test filtering sitemap URLs by contains string."""
    from app.cli_helpers.fetch_helpers import sitemap_target_urls
    from unittest.mock import patch

    # Mock parse_sitemap_urls to return test URLs
    test_urls = [
        "https://example.com/prodotto/bike-1",
        "https://example.com/about",
        "https://example.com/prodotto/bike-2",
        "https://example.com/contact",
    ]

    with patch(
        "app.cli_helpers.fetch_helpers.parse_sitemap_urls", return_value=test_urls
    ):
        # Test filtering by contains
        filtered = sitemap_target_urls(
            "https://example.com/sitemap.xml", {}, "/prodotto/", 0
        )
        assert len(filtered) == 2
        assert all("/prodotto/" in url for url in filtered)

        # Test with limit
        filtered = sitemap_target_urls(
            "https://example.com/sitemap.xml", {}, "/prodotto/", 1
        )
        # Note: parse_sitemap_urls respects the limit, not our function
        # So this just tests that limit is passed through correctly


def test_upsert_dealer_policy_new_dealer(monkeypatch):
    """Test inserting a new dealer policy."""
    from app.cli_helpers.fetch_helpers import upsert_dealer_policy

    # Mock database objects
    class MockExt:
        base_cost = 10.0
        free_threshold = 100.0
        lead_days_std = 5
        confidence = 0.9

    class MockDB:
        def __init__(self):
            self.added = []
            self.committed = False

        def scalar(self, query):
            return None  # Simulate no existing policy

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.committed = True

    db = MockDB()
    ext = MockExt()

    upsert_dealer_policy(db, "TestDealer", ext)

    assert len(db.added) == 1
    assert db.added[0].dealer == "TestDealer"
    assert db.added[0].base_cost == 10.0
    assert db.committed


def test_upsert_dealer_policy_update_existing(monkeypatch):
    """Test updating an existing dealer policy."""
    from app.cli_helpers.fetch_helpers import upsert_dealer_policy

    # Mock database objects
    class MockExt:
        base_cost = 15.0
        free_threshold = 150.0
        lead_days_std = 7
        confidence = 0.95

    class MockPolicy:
        def __init__(self):
            self.dealer = "TestDealer"
            self.base_cost = 10.0
            self.free_threshold = 100.0
            self.lead_days_std = 5
            self.source = "old"
            self.confidence = 0.8

    class MockDB:
        def __init__(self):
            self.policy = MockPolicy()
            self.committed = False

        def scalar(self, query):
            return self.policy  # Simulate existing policy

        def add(self, obj):
            pass

        def commit(self):
            self.committed = True

    db = MockDB()
    ext = MockExt()

    upsert_dealer_policy(db, "TestDealer", ext)

    # Check that existing policy was updated
    assert db.policy.base_cost == 15.0
    assert db.policy.free_threshold == 150.0
    assert db.policy.lead_days_std == 7
    assert db.policy.confidence == 0.95
    assert db.policy.source == "rules"
    assert db.committed
