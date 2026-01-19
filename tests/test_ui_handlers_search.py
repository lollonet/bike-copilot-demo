"""Unit tests for app.ui_handlers_search module."""

from __future__ import annotations

import pytest


def test_handle_search_request_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handle_search_request with successful API response."""
    import app.ui_handlers_search as handler_mod

    # Mock _do_search to return fake results
    def fake_do_search(*args, **kwargs):
        return (
            [("Brand1", "PN123", "Product", "€50.00", "Dealer1", "Sì")],
            [("€50.00 - Dealer1", "1")],
            {"1": "PN123"},
            "Trovati 1 risultati",
        )

    monkeypatch.setattr(handler_mod, "_do_search", fake_do_search)

    # Mock api_post_silent to return facets
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "speed": {"11-speed": 1},
                "freehub": {"Shimano": 1},
                "brake": {"Disc": 1},
                "axle": {"Thru-axle": 1},
                "rotor": {"160mm": 1},
                "category": {"MTB": 1},
                "supplier": {"Dealer1": 1},
                "totals": {"products": 1},
                "price": {"min": 50.0, "max": 50.0},
            }

    def fake_api_post_silent(path, payload, timeout):
        return DummyResponse()

    monkeypatch.setattr(handler_mod, "api_post_silent", fake_api_post_silent)

    # Call handler
    result = handler_mod.handle_search_request(
        query="test",
        speed="",
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget=None,
        category="",
        suppliers_sel=None,
        in_stock_only=False,
    )

    # Verify structure
    assert len(result.rows) == 1
    assert result.rows[0][0] == "Brand1"
    assert result.default_label == "€50.00 - Dealer1"
    assert result.message == "Trovati 1 risultati"

    # Verify facets were populated
    assert "11-speed" in result.speed.choices
    assert result.speed.interactive is True
    assert "Shimano" in result.freehub.choices
    assert "Disc" in result.brake.choices
    assert "MTB" in result.category.choices

    # Verify budget update (slider_max is max(100, price_max) so with price=50, slider_max=100)
    assert result.budget.slider_max == 100
    assert "Prezzo min/max" in (result.budget.info or "")

    # Verify active filters (should be empty with no filters applied)
    assert result.active_filters == []


def test_handle_search_request_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handle_search_request when facets API fails."""
    import app.ui_handlers_search as handler_mod

    # Mock _do_search
    def fake_do_search(*args, **kwargs):
        return ([], [], {}, "Trovati 0 risultati")

    monkeypatch.setattr(handler_mod, "_do_search", fake_do_search)

    # Mock api_post_silent to return error
    class ErrorResponse:
        status_code = 500

        def json(self):
            return {}

    def fake_api_post_silent(path, payload, timeout):
        return ErrorResponse()

    monkeypatch.setattr(handler_mod, "api_post_silent", fake_api_post_silent)

    # Call handler
    result = handler_mod.handle_search_request(
        query="test",
        speed="",
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget=None,
        category="",
        suppliers_sel=None,
        in_stock_only=False,
    )

    # Verify empty results
    assert result.rows == []
    assert result.default_label is None

    # Verify facets are empty (graceful degradation)
    assert result.speed.choices == []
    assert result.speed.interactive is False
    assert result.freehub.choices == []
    assert result.category.choices == []


def test_handle_search_request_with_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test handle_search_request with filters applied."""
    import app.ui_handlers_search as handler_mod

    # Mock _do_search
    def fake_do_search(*args, **kwargs):
        return (
            [("Brand1", "PN123", "Product", "€100.00", "Dealer1", "Sì")],
            [("€100.00 - Dealer1", "1")],
            {"1": "PN123"},
            "Trovati 1 risultati",
        )

    monkeypatch.setattr(handler_mod, "_do_search", fake_do_search)

    # Mock api_post_silent
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "speed": {"12-speed": 1},
                "freehub": {},
                "brake": {},
                "axle": {},
                "rotor": {},
                "category": {"Road": 1},
                "supplier": {"Dealer1": 1},
                "totals": {"products": 1},
                "price": {"min": 100.0, "max": 100.0},
            }

    monkeypatch.setattr(
        handler_mod, "api_post_silent", lambda *args, **kwargs: DummyResponse()
    )

    # Call handler with filters
    result = handler_mod.handle_search_request(
        query="test",
        speed="12-speed",
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget="150",
        category="Road",
        suppliers_sel=["Dealer1"],
        in_stock_only=True,
    )

    # Verify active filters list
    assert "category:Road" in result.active_filters
    assert "speed:12-speed" in result.active_filters
    assert "suppliers:Dealer1" in result.active_filters
    assert "in_stock:true" in result.active_filters
    assert "budget:<= 150" in result.active_filters


def test_handle_search_request_facet_value_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that facet values are reset when they disappear from choices."""
    import app.ui_handlers_search as handler_mod

    # Mock _do_search
    def fake_do_search(*args, **kwargs):
        return (
            [("Brand1", "PN123", "Product", "€50.00", "Dealer1", "Sì")],
            [("€50.00 - Dealer1", "1")],
            {"1": "PN123"},
            "Trovati 1 risultati",
        )

    monkeypatch.setattr(handler_mod, "_do_search", fake_do_search)

    # Mock api_post_silent - return different speed options than what user selected
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "speed": {
                    "11-speed": 1
                },  # User selected "12-speed" but only "11-speed" available
                "freehub": {},
                "brake": {},
                "axle": {},
                "rotor": {},
                "category": {},
                "supplier": {},
                "totals": {"products": 1},
                "price": {},
            }

    monkeypatch.setattr(
        handler_mod, "api_post_silent", lambda *args, **kwargs: DummyResponse()
    )

    # Call handler with speed="12-speed" which won't be in returned choices
    result = handler_mod.handle_search_request(
        query="test",
        speed="12-speed",  # This will be reset
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget=None,
        category="",
        suppliers_sel=None,
        in_stock_only=False,
    )

    # Verify speed value was reset to empty string
    assert result.speed.value == ""
    assert "11-speed" in result.speed.choices
