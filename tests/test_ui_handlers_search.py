"""Tests for search handler business logic."""

from __future__ import annotations


def test_handle_search_request_basic(monkeypatch):
    """Test successful search with facets."""
    from app import ui_handlers_search
    from app.types import OfferItem, SearchResponse

    # Mock search to return fake results
    def fake_search(req):
        return SearchResponse(
            items=[
                OfferItem(
                    id=1,
                    brand="Brand1",
                    mpn="PN123",
                    supplier="Supplier1",
                    price=50.0,
                    in_stock=True,
                    lead_time_days=5,
                    score=0.95,
                )
            ]
        )

    monkeypatch.setattr(ui_handlers_search, "search", fake_search)

    # Mock api_post_silent to return facets
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "speed": {"11-speed": 1},
                "freehub": {"Shimano": 1},
                "brake": {"Centerlock": 1},
                "axle": {"Thru Axle 12mm": 1},
                "rotor": {"160mm": 1},
                "supplier": {"Supplier1": 1},
                "category": {"MTB": 1},
                "totals": {"products": 1},
                "price": {"min": 50.0, "max": 50.0},
            }

    def fake_api_post_silent(url, payload, timeout):
        return DummyResponse()

    monkeypatch.setattr(ui_handlers_search, "api_post_silent", fake_api_post_silent)

    # Call handler
    result = ui_handlers_search.handle_search_request(
        query="test",
        speed="",
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget=None,
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
    )

    # Verify results
    assert len(result.rows) == 1
    assert result.rows[0][0] == 1  # ID
    assert result.rows[0][1] == "Brand1"  # Brand
    assert result.rows[0][2] == "PN123"  # MPN
    assert "11-speed" in result.speed.choices
    assert result.speed.interactive is True
    assert result.budget.slider_max == 100  # max(100, price_max)
    assert result.message == "Trovate 1 offerte"


def test_handle_search_request_api_error(monkeypatch):
    """Test graceful degradation when facets API fails."""
    from app import ui_handlers_search
    from app.types import OfferItem, SearchResponse

    # Mock search to return results
    def fake_search(req):
        return SearchResponse(
            items=[
                OfferItem(
                    id=1,
                    brand="Brand1",
                    mpn="PN123",
                    supplier="Supplier1",
                    price=50.0,
                    in_stock=True,
                    lead_time_days=5,
                    score=0.95,
                )
            ]
        )

    monkeypatch.setattr(ui_handlers_search, "search", fake_search)

    # Mock api_post_silent to return error
    class ErrorResponse:
        status_code = 500

        def json(self):
            return {}

    def fake_api_post_silent(url, payload, timeout):
        return ErrorResponse()

    monkeypatch.setattr(ui_handlers_search, "api_post_silent", fake_api_post_silent)

    # Call handler
    result = ui_handlers_search.handle_search_request(
        query="test",
        speed="",
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget=None,
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
    )

    # Verify search still works even though facets failed
    assert len(result.rows) == 1
    assert result.message == "Trovate 1 offerte"
    # Facets should be empty/default
    assert result.speed.choices == []
    assert result.speed.interactive is False


def test_handle_search_request_with_filters(monkeypatch):
    """Test active filters list generation."""
    from app import ui_handlers_search
    from app.types import SearchResponse

    # Mock search to return empty results
    def fake_search(req):
        return SearchResponse(items=[])

    monkeypatch.setattr(ui_handlers_search, "search", fake_search)

    # Mock API with minimal response
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "speed": {},
                "freehub": {},
                "brake": {},
                "axle": {},
                "rotor": {},
                "supplier": {},
                "category": {},
                "totals": {"products": 0},
                "price": {},
            }

    def fake_api_post_silent(url, payload, timeout):
        return DummyResponse()

    monkeypatch.setattr(ui_handlers_search, "api_post_silent", fake_api_post_silent)

    # Call with filters (use valid enum values: HG, XD, MS for freehub)
    result = ui_handlers_search.handle_search_request(
        query="test",
        speed="11-speed",
        freehub="HG",  # Valid Freehub enum value
        brake="",
        axle="",
        rotor="",
        budget="100",
        category="MTB",
        suppliers_sel=["Supplier1"],
        in_stock_only=True,
    )

    # Verify active filters list
    assert "category:MTB" in result.active_filters
    assert "suppliers:Supplier1" in result.active_filters
    assert "in_stock:true" in result.active_filters
    assert "speed:11-speed" in result.active_filters
    assert "freehub:HG" in result.active_filters
    assert any("budget" in f for f in result.active_filters)


def test_handle_search_request_facet_value_reset(monkeypatch):
    """Test facet values reset when no longer in choices."""
    from app import ui_handlers_search
    from app.types import SearchResponse

    # Mock search
    def fake_search(req):
        return SearchResponse(items=[])

    monkeypatch.setattr(ui_handlers_search, "search", fake_search)

    # Mock API returning only "11-speed" but user has "12-speed" selected
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "speed": {"11-speed": 1},  # Only 11-speed available
                "freehub": {},
                "brake": {},
                "axle": {},
                "rotor": {},
                "supplier": {},
                "category": {},
                "totals": {"products": 1},
                "price": {},
            }

    def fake_api_post_silent(url, payload, timeout):
        return DummyResponse()

    monkeypatch.setattr(ui_handlers_search, "api_post_silent", fake_api_post_silent)

    # Call with "12-speed" selected (not in choices)
    result = ui_handlers_search.handle_search_request(
        query="test",
        speed="12-speed",  # User selected this
        freehub="",
        brake="",
        axle="",
        rotor="",
        budget=None,
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
    )

    # Verify value was reset to "" because "12-speed" not in choices
    assert result.speed.value == ""
    assert "11-speed" in result.speed.choices
    assert "12-speed" not in result.speed.choices
