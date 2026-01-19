"""Unit tests for app.api_client module."""

from __future__ import annotations

from typing import Any

import pytest


class DummyResponse:
    """Mock httpx.Response for testing."""

    def __init__(self, status_code: int, json_data: dict[str, Any] | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self) -> dict[str, Any]:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                "HTTP error",
                request=None,
                response=self,  # type: ignore[arg-type]
            )


class DummyClient:
    """Mock httpx.Client for testing."""

    def __init__(self, response: DummyResponse):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get(self, url: str, **kwargs) -> DummyResponse:
        return self.response

    def post(self, url: str, **kwargs) -> DummyResponse:
        return self.response


def test_api_get_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_get with successful response."""
    import app.api_client as api_client

    test_data = {"dealers": [{"name": "Dealer1"}]}
    dummy_resp = DummyResponse(200, test_data)

    def mock_client(*args, **kwargs):
        return DummyClient(dummy_resp)

    import httpx

    monkeypatch.setattr(httpx, "Client", mock_client)

    result = api_client.api_get("/dealers")
    assert result == test_data


def test_api_get_with_custom_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_get with custom timeout."""
    import app.api_client as api_client

    test_data = {"status": "ok"}
    dummy_resp = DummyResponse(200, test_data)

    def mock_client(*args, **kwargs):
        # Verify timeout was passed
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 30.0
        return DummyClient(dummy_resp)

    import httpx

    monkeypatch.setattr(httpx, "Client", mock_client)

    result = api_client.api_get("/status", timeout=30.0)
    assert result == test_data


def test_api_get_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_get raises HTTPStatusError on non-2xx response."""
    import app.api_client as api_client

    dummy_resp = DummyResponse(404, {"error": "Not found"})

    def mock_client(*args, **kwargs):
        return DummyClient(dummy_resp)

    import httpx

    monkeypatch.setattr(httpx, "Client", mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        api_client.api_get("/nonexistent")


def test_api_post_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_post with successful response."""
    import app.api_client as api_client

    payload = {"items": [{"offer_id": 1, "qty": 2}]}
    response_data = {"quote_id": 123, "total": 200.0}
    dummy_resp = DummyResponse(200, response_data)

    def mock_client(*args, **kwargs):
        return DummyClient(dummy_resp)

    import httpx

    monkeypatch.setattr(httpx, "Client", mock_client)

    result = api_client.api_post("/quote", payload)
    assert result == response_data


def test_api_post_with_custom_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_post with custom timeout."""
    import app.api_client as api_client

    payload = {"query": "test"}
    response_data = {"results": []}
    dummy_resp = DummyResponse(200, response_data)

    def mock_client(*args, **kwargs):
        # Verify timeout was passed
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 10.0
        return DummyClient(dummy_resp)

    import httpx

    monkeypatch.setattr(httpx, "Client", mock_client)

    result = api_client.api_post("/search", payload, timeout=10.0)
    assert result == response_data


def test_api_post_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_post raises HTTPStatusError on non-2xx response."""
    import app.api_client as api_client

    payload = {"invalid": "data"}
    dummy_resp = DummyResponse(400, {"error": "Bad request"})

    def mock_client(*args, **kwargs):
        return DummyClient(dummy_resp)

    import httpx

    monkeypatch.setattr(httpx, "Client", mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        api_client.api_post("/endpoint", payload)


def test_api_post_silent_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_post_silent with successful response."""
    import app.api_client as api_client

    payload = {"data": "test"}
    response_data = {"success": True}
    dummy_resp = DummyResponse(200, response_data)

    def mock_post(*args, **kwargs):
        return dummy_resp

    import httpx

    monkeypatch.setattr(httpx, "post", mock_post)

    result = api_client.api_post_silent("/endpoint", payload)
    assert result.status_code == 200
    assert result.json() == response_data


def test_api_post_silent_no_raise_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test api_post_silent does not raise on HTTP error."""
    import app.api_client as api_client

    payload = {"data": "test"}
    dummy_resp = DummyResponse(500, {"error": "Internal error"})

    def mock_post(*args, **kwargs):
        return dummy_resp

    import httpx

    monkeypatch.setattr(httpx, "post", mock_post)

    # Should not raise - return response object for manual inspection
    result = api_client.api_post_silent("/endpoint", payload)
    assert result.status_code == 500


def test_api_client_auth_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that API client correctly reads auth from environment."""
    import app.api_client as api_client

    # Set auth credentials via environment
    monkeypatch.setenv("APP_BASIC_USER", "testuser")
    monkeypatch.setenv("APP_BASIC_PASS", "testpass")

    # Reload module to pick up new env vars
    import importlib

    importlib.reload(api_client)

    # Verify credentials are set (internal detail, but important for coverage)
    assert api_client._auth_credentials == ("testuser", "testpass")


def test_api_client_no_auth_when_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that API client doesn't set auth if credentials are incomplete."""
    import app.api_client as api_client

    # Set only username, no password
    monkeypatch.setenv("APP_BASIC_USER", "testuser")
    monkeypatch.delenv("APP_BASIC_PASS", raising=False)

    # Reload module to pick up new env vars
    import importlib

    importlib.reload(api_client)

    # Verify credentials are NOT set when incomplete
    assert api_client._auth_credentials is None
