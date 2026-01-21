"""Tests for service CLI commands and helpers."""

from __future__ import annotations


def test_env_value():
    """Test environment variable extraction."""
    from app.cli_helpers.service_helpers import env_value
    import os

    # Test with existing variable
    os.environ["TEST_VAR"] = "  test_value  "
    assert env_value("TEST_VAR") == "test_value"

    # Test with missing variable
    assert env_value("NONEXISTENT_VAR") == ""

    # Test with None
    assert env_value(None) == ""

    # Cleanup
    del os.environ["TEST_VAR"]


def test_build_http_client():
    """Test HTTP client creation."""
    from app.cli_helpers.service_helpers import build_http_client

    client = build_http_client()

    assert client.timeout.read == 15.0
    assert client.headers["User-Agent"] == "BikeCopilotBot/0.1"
    assert client.follow_redirects is True

    client.close()


def test_build_login_payload_items():
    """Test login payload item construction."""
    from app.cli_helpers.service_helpers import build_login_payload_items
    from app.dealers import DealerLoginConfig

    login_cfg = DealerLoginConfig(
        mode="form",
        url="https://example.com/login",
        username_field="user",
        password_field="pass",
        extra_fields={"extra": "field"},
    )

    items = build_login_payload_items(login_cfg, "testuser", "testpass")

    assert ("extra", "field") in items
    assert ("user", "testuser") in items
    assert ("pass", "testpass") in items
    assert len(items) == 3


def test_build_login_payload_items_no_fields():
    """Test login payload with no username/password fields."""
    from app.cli_helpers.service_helpers import build_login_payload_items
    from app.dealers import DealerLoginConfig

    login_cfg = DealerLoginConfig(
        mode="form",
        url="https://example.com/login",
        extra_fields={"key": "value"},
    )

    items = build_login_payload_items(login_cfg, "user", "pass")

    assert items == [("key", "value")]


def test_build_spa_payload():
    """Test SPA login payload construction."""
    from app.cli_helpers.service_helpers import build_spa_payload
    from app.dealers import DealerLoginConfig

    login_cfg = DealerLoginConfig(
        mode="spa",
        url="https://example.com/api/auth",
        username_field="username",
        password_field="password",
        extra_fields={"client_id": "app123"},
    )

    payload = build_spa_payload(login_cfg, "testuser", "testpass")

    assert payload["username"] == "testuser"
    assert payload["password"] == "testpass"
    assert payload["client_id"] == "app123"


def test_build_spa_payload_with_base64():
    """Test SPA payload with base64 encoding."""
    from app.cli_helpers.service_helpers import build_spa_payload
    from app.dealers import DealerLoginConfig
    import base64

    login_cfg = DealerLoginConfig(
        mode="spa",
        url="https://example.com/api/auth",
        username_field="username",
        password_field="password",
        encode_base64=True,
    )

    payload = build_spa_payload(login_cfg, "testuser", "testpass")

    expected_user = base64.b64encode(b"testuser").decode()
    expected_pass = base64.b64encode(b"testpass").decode()

    assert payload["username"] == expected_user
    assert payload["password"] == expected_pass


def test_extract_spa_token_from_json():
    """Test token extraction from JSON response."""
    from app.cli_helpers.service_helpers import extract_spa_token
    from unittest.mock import Mock

    # Test with 'token' field
    resp = Mock()
    resp.json.return_value = {"token": "abc123"}

    token = extract_spa_token(resp)
    assert token == "abc123"

    # Test with 'access_token' field
    resp.json.return_value = {"access_token": "xyz789"}

    token = extract_spa_token(resp)
    assert token == "xyz789"


def test_extract_spa_token_no_token():
    """Test token extraction when no token present."""
    from app.cli_helpers.service_helpers import extract_spa_token
    from unittest.mock import Mock

    resp = Mock()
    resp.json.return_value = {"user": "test"}

    token = extract_spa_token(resp)
    assert token is None


def test_extract_spa_token_invalid_json():
    """Test token extraction with invalid JSON."""
    from app.cli_helpers.service_helpers import extract_spa_token
    from unittest.mock import Mock

    resp = Mock()
    resp.json.side_effect = ValueError("Invalid JSON")

    token = extract_spa_token(resp)
    assert token is None


def test_extract_spa_token_non_dict():
    """Test token extraction with non-dict JSON."""
    from app.cli_helpers.service_helpers import extract_spa_token
    from unittest.mock import Mock

    resp = Mock()
    resp.json.return_value = ["not", "a", "dict"]

    token = extract_spa_token(resp)
    assert token is None


def test_can_sync_catalog_mode_filter():
    """Test catalog sync mode filtering."""
    from app.cli_helpers.service_helpers import can_sync_catalog
    from app.dealers import DealerConfig, DealerAuthConfig, DealerSeeds
    from pathlib import Path

    cfg = DealerConfig(
        key="test",
        name="test",
        type="web",
        base_url_env=None,
        platform=None,
        mapping="test.yaml",
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env=None, username_env=None, password_env=None, cookie_env=None
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=None,
    )
    mapping_path = Path("test.yaml")

    # Test "all" mode
    assert can_sync_catalog(cfg, "all", mapping_path) is True

    # Test "catalogo" mode
    assert can_sync_catalog(cfg, "catalogo", mapping_path) is True

    # Test "policy" mode
    assert can_sync_catalog(cfg, "policy", mapping_path) is False


def test_can_sync_catalog_type_filter():
    """Test catalog sync type filtering."""
    from app.cli_helpers.service_helpers import can_sync_catalog
    from app.dealers import DealerConfig, DealerAuthConfig, DealerSeeds
    from pathlib import Path

    cfg = DealerConfig(
        key="test",
        name="test",
        type="csv",  # Not "web"
        base_url_env=None,
        platform=None,
        mapping="test.yaml",
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env=None, username_env=None, password_env=None, cookie_env=None
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=None,
    )
    mapping_path = Path("test.yaml")

    assert can_sync_catalog(cfg, "all", mapping_path) is False


def test_can_sync_catalog_mapping_filter():
    """Test catalog sync mapping requirement."""
    from app.cli_helpers.service_helpers import can_sync_catalog
    from app.dealers import DealerConfig, DealerAuthConfig, DealerSeeds

    cfg = DealerConfig(
        key="test",
        name="test",
        type="web",
        base_url_env=None,
        platform=None,
        mapping=None,
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env=None, username_env=None, password_env=None, cookie_env=None
        ),
        seeds=DealerSeeds(urls=[], sitemap=None),
        login=None,
    )

    # No mapping configured
    assert can_sync_catalog(cfg, "all", None) is False


def test_collect_dealer_urls_from_seeds():
    """Test URL collection from dealer seeds."""
    from app.cli_helpers.service_helpers import collect_dealer_urls, DealerSession
    from app.dealers import DealerConfig, DealerAuthConfig, DealerSeeds
    from unittest.mock import Mock

    cfg = DealerConfig(
        key="test",
        name="test",
        type="web",
        base_url_env=None,
        platform=None,
        mapping=None,
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env=None, username_env=None, password_env=None, cookie_env=None
        ),
        seeds=DealerSeeds(
            urls=["http://example.com/product1", "http://example.com/product2"],
            sitemap=None,
        ),
        login=None,
    )

    mock_client = Mock()
    session = DealerSession(mock_client, None)

    def mock_parse_sitemap(url, headers, limit, session):
        return []

    urls = collect_dealer_urls(cfg, session, mock_parse_sitemap)

    assert len(urls) == 2
    assert "http://example.com/product1" in urls
    assert "http://example.com/product2" in urls


def test_collect_dealer_urls_with_sitemap():
    """Test URL collection with sitemap."""
    from app.cli_helpers.service_helpers import collect_dealer_urls, DealerSession
    from app.dealers import DealerConfig, DealerAuthConfig, DealerSeeds
    from unittest.mock import Mock

    cfg = DealerConfig(
        key="test",
        name="test",
        type="web",
        base_url_env=None,
        platform=None,
        mapping=None,
        policy_url=None,
        auth=DealerAuthConfig(
            mode_env=None, username_env=None, password_env=None, cookie_env=None
        ),
        seeds=DealerSeeds(
            urls=["http://example.com/product1"],
            sitemap="http://example.com/sitemap.xml",
        ),
        login=None,
    )

    mock_client = Mock()
    session = DealerSession(mock_client, None)

    def mock_parse_sitemap(url, headers, limit, session):
        if "sitemap" in url:
            return ["http://example.com/product2", "http://example.com/product3"]
        return []

    urls = collect_dealer_urls(cfg, session, mock_parse_sitemap)

    assert len(urls) == 3
    assert "http://example.com/product1" in urls
    assert "http://example.com/product2" in urls
    assert "http://example.com/product3" in urls


def test_dealer_session_close():
    """Test DealerSession close method."""
    from app.cli_helpers.service_helpers import DealerSession
    from unittest.mock import Mock

    mock_client = Mock()
    session = DealerSession(mock_client, None)

    session.close()

    mock_client.close.assert_called_once()
