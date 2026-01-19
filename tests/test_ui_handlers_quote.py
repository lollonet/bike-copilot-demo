"""Tests for quote handler business logic."""

from __future__ import annotations


def test_render_local_quote_with_items(monkeypatch):
    """Test render_local_quote with valid items."""
    from app import ui_handlers_quote

    # Mock database session
    class MockProduct:
        brand = "Brand1"
        mpn = "MPN1"
        name = "Product Name"

    class MockOffer:
        product = MockProduct()
        supplier = "Supplier1"
        price = 50.0
        in_stock = True
        lead_time_days = 5

    class MockDB:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, model, oid):
            if oid == 123:
                return MockOffer()
            return None

    def mock_session_local():
        return MockDB()

    monkeypatch.setattr(ui_handlers_quote, "SessionLocal", mock_session_local)

    # Mock render_quote
    def mock_render_quote(ctx):
        assert ctx["customer_name"] == "Customer"
        assert ctx["customer_contact"] == "contact@example.com"
        assert ctx["validity_days"] == 30
        assert ctx["notes"] == "Test notes"
        assert len(ctx["items"]) == 1
        assert ctx["items"][0]["brand"] == "Brand1"
        return "/path/to/quote.html", "/path/to/quote.pdf"

    monkeypatch.setattr(ui_handlers_quote, "render_quote", mock_render_quote)

    # Call handler
    html_path, pdf_path, file_url = ui_handlers_quote.render_local_quote(
        items=[{"offer_id": 123, "qty": 2}],
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="Test notes",
    )

    assert html_path == "/path/to/quote.html"
    assert pdf_path == "/path/to/quote.pdf"
    assert file_url == ""


def test_render_local_quote_empty_items(monkeypatch):
    """Test render_local_quote with no items."""
    from app import ui_handlers_quote

    # Mock database session returning no offers
    class MockDB:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, model, oid):
            return None

    def mock_session_local():
        return MockDB()

    monkeypatch.setattr(ui_handlers_quote, "SessionLocal", mock_session_local)

    # Call handler with items that won't be found
    html_path, pdf_path, file_url = ui_handlers_quote.render_local_quote(
        items=[{"offer_id": 999, "qty": 1}],
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="",
    )

    assert html_path == "Nessun elemento nel carrello"
    assert pdf_path == ""
    assert file_url == ""


def test_handle_quote_request_with_cart(monkeypatch):
    """Test handle_quote_request using cart items."""
    from app import ui_handlers_quote

    # Mock API response
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "html_path": "/path/to/quote.html",
                "pdf_path": "/path/to/quote.pdf",
                "file_url": "https://example.com/quote.pdf",
            }

    def fake_api_post_silent(url, payload, timeout):
        assert url == "/quote"
        assert len(payload["items"]) == 2
        assert payload["items"][0]["offer_id"] == 1
        assert payload["items"][0]["qty"] == 2
        assert payload["items"][1]["offer_id"] == 2
        assert payload["items"][1]["qty"] == 1
        assert payload["customer_name"] == "Customer"
        assert payload["customer_contact"] == "contact@example.com"
        assert payload["validity_days"] == 30
        assert payload["notes"] == "Test notes"
        return DummyResponse()

    monkeypatch.setattr(ui_handlers_quote, "api_post_silent", fake_api_post_silent)

    # Call handler with cart
    cart = {
        1: {"brand": "Brand1", "mpn": "MPN1", "price": 50.0, "qty": 2},
        2: {"brand": "Brand2", "mpn": "MPN2", "price": 75.0, "qty": 1},
    }

    html_path, pdf_path, file_url = ui_handlers_quote.handle_quote_request(
        offer_label=None,
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="Test notes",
        cart=cart,
    )

    assert html_path == "/path/to/quote.html"
    assert pdf_path == "/path/to/quote.pdf"
    assert file_url == "https://example.com/quote.pdf"


def test_handle_quote_request_with_single_offer(monkeypatch):
    """Test handle_quote_request with single offer (no cart)."""
    from app import ui_handlers_quote

    # Mock API response
    class DummyResponse:
        status_code = 200

        def json(self):
            return {
                "html_path": "/path/to/quote.html",
                "pdf_path": "/path/to/quote.pdf",
                "file_url": "https://example.com/quote.pdf",
            }

    def fake_api_post_silent(url, payload, timeout):
        assert len(payload["items"]) == 1
        assert payload["items"][0]["offer_id"] == 123
        assert payload["items"][0]["qty"] == 1
        return DummyResponse()

    monkeypatch.setattr(ui_handlers_quote, "api_post_silent", fake_api_post_silent)

    # Call handler with single offer
    html_path, pdf_path, file_url = ui_handlers_quote.handle_quote_request(
        offer_label="123 · Brand1 MPN1",
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="Test notes",
        cart={},
    )

    assert html_path == "/path/to/quote.html"
    assert pdf_path == "/path/to/quote.pdf"
    assert file_url == "https://example.com/quote.pdf"


def test_handle_quote_request_no_offer_no_cart():
    """Test handle_quote_request with no offer and no cart."""
    from app.ui_handlers_quote import handle_quote_request

    html_path, pdf_path, file_url = handle_quote_request(
        offer_label=None,
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="",
        cart={},
    )

    assert html_path == "Seleziona un'offerta"
    assert pdf_path == ""
    assert file_url == ""


def test_handle_quote_request_invalid_offer_label():
    """Test handle_quote_request with invalid offer label."""
    from app.ui_handlers_quote import handle_quote_request

    html_path, pdf_path, file_url = handle_quote_request(
        offer_label="invalid-label",
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="",
        cart={},
    )

    assert html_path == "Seleziona un'offerta"
    assert pdf_path == ""
    assert file_url == ""


def test_handle_quote_request_api_failure_fallback(monkeypatch):
    """Test handle_quote_request falls back to local rendering on API failure."""
    from app import ui_handlers_quote

    # Mock API to return error
    class ErrorResponse:
        status_code = 500

        def json(self):
            return {}

    def fake_api_post_silent(url, payload, timeout):
        return ErrorResponse()

    monkeypatch.setattr(ui_handlers_quote, "api_post_silent", fake_api_post_silent)

    # Mock render_local_quote to verify fallback
    fallback_called = []

    def mock_render_local_quote(items, customer, contact, validity, notes):
        fallback_called.append(True)
        return "/local/quote.html", "/local/quote.pdf", ""

    monkeypatch.setattr(
        ui_handlers_quote, "render_local_quote", mock_render_local_quote
    )

    # Call handler
    html_path, pdf_path, file_url = ui_handlers_quote.handle_quote_request(
        offer_label="123 · Brand1 MPN1",
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="",
        cart={},
    )

    # Verify fallback was called
    assert len(fallback_called) == 1
    assert html_path == "/local/quote.html"
    assert pdf_path == "/local/quote.pdf"


def test_handle_quote_request_api_exception_fallback(monkeypatch):
    """Test handle_quote_request falls back to local rendering on API exception."""
    from app import ui_handlers_quote

    # Mock API to raise exception
    def fake_api_post_silent(url, payload, timeout):
        raise ConnectionError("API unavailable")

    monkeypatch.setattr(ui_handlers_quote, "api_post_silent", fake_api_post_silent)

    # Mock render_local_quote to verify fallback
    fallback_called = []

    def mock_render_local_quote(items, customer, contact, validity, notes):
        fallback_called.append(True)
        return "/local/quote.html", "/local/quote.pdf", ""

    monkeypatch.setattr(
        ui_handlers_quote, "render_local_quote", mock_render_local_quote
    )

    # Call handler
    html_path, pdf_path, file_url = ui_handlers_quote.handle_quote_request(
        offer_label="123 · Brand1 MPN1",
        customer="Customer",
        contact="contact@example.com",
        validity=30,
        notes="",
        cart={},
    )

    # Verify fallback was called
    assert len(fallback_called) == 1
    assert html_path == "/local/quote.html"
    assert pdf_path == "/local/quote.pdf"
