"""Tests for cart handler business logic."""

from __future__ import annotations


def test_parse_offer_id_from_label_valid():
    """Test parse_offer_id_from_label with valid inputs."""
    from app.ui_handlers_cart import parse_offer_id_from_label

    assert parse_offer_id_from_label("123 · Brand MPN") == 123
    assert parse_offer_id_from_label("456 · Another Brand · Supplier") == 456
    assert parse_offer_id_from_label("1 · Single") == 1


def test_parse_offer_id_from_label_invalid():
    """Test parse_offer_id_from_label with invalid inputs."""
    from app.ui_handlers_cart import parse_offer_id_from_label

    assert parse_offer_id_from_label(None) is None
    assert parse_offer_id_from_label("") is None
    assert parse_offer_id_from_label("no-number") is None
    assert parse_offer_id_from_label("abc · Brand") is None


def test_build_cart_rows_empty():
    """Test build_cart_rows with empty cart."""
    from app.ui_handlers_cart import build_cart_rows

    rows, labels = build_cart_rows({})

    assert rows == []
    assert labels == []


def test_build_cart_rows_multiple_items():
    """Test build_cart_rows with multiple items."""
    from app.ui_handlers_cart import build_cart_rows

    cart = {
        1: {
            "brand": "Brand1",
            "mpn": "MPN1",
            "supplier": "Supplier1",
            "price": 50.0,
            "qty": 2,
        },
        2: {
            "brand": "Brand2",
            "mpn": "MPN2",
            "supplier": "Supplier2",
            "price": 75.5,
            "qty": 1,
        },
    }

    rows, labels = build_cart_rows(cart)

    # Check rows
    assert len(rows) == 2
    assert rows[0] == [1, "Brand1", "MPN1", "Supplier1", 50.0, 2, 100.0]
    assert rows[1] == [2, "Brand2", "MPN2", "Supplier2", 75.5, 1, 75.5]

    # Check labels
    assert len(labels) == 2
    assert labels[0] == "1 · Brand1 MPN1"
    assert labels[1] == "2 · Brand2 MPN2"


def test_calculate_cart_totals_no_vat(monkeypatch):
    """Test calculate_cart_totals without VAT."""
    from app.ui_handlers_cart import calculate_cart_totals

    monkeypatch.setenv("APP_VAT", "0")

    cart = {
        1: {"price": 50.0, "qty": 2},
        2: {"price": 75.5, "qty": 1},
    }

    subtotal, vat_rate, vat, total = calculate_cart_totals(cart)

    assert subtotal == 175.5
    assert vat_rate == 0.0
    assert vat == 0.0
    assert total == 175.5


def test_calculate_cart_totals_with_vat(monkeypatch):
    """Test calculate_cart_totals with VAT."""
    from app.ui_handlers_cart import calculate_cart_totals

    monkeypatch.setenv("APP_VAT", "0.22")

    cart = {
        1: {"price": 100.0, "qty": 1},
        2: {"price": 50.0, "qty": 2},
    }

    subtotal, vat_rate, vat, total = calculate_cart_totals(cart)

    assert subtotal == 200.0
    assert vat_rate == 0.22
    assert vat == 44.0
    assert total == 244.0


def test_format_totals_markdown(monkeypatch):
    """Test format_totals_markdown output."""
    from app.ui_handlers_cart import format_totals_markdown

    monkeypatch.setenv("APP_VAT", "0.22")

    cart = {
        1: {"price": 100.0, "qty": 1},
    }

    result = format_totals_markdown(cart)

    assert "€100.00" in result
    assert "22%" in result
    assert "€22.00" in result
    assert "€122.00" in result


def test_handle_offer_select_valid():
    """Test handle_offer_select with valid offer."""
    from app.ui_handlers_cart import handle_offer_select

    mapping = {
        123: {"brand": "Brand1", "mpn": "MPN1", "supplier": "Supplier1", "price": 50.0},
    }

    result = handle_offer_select("123 · Brand1 MPN1", mapping)

    assert "Offerta 123" in result
    assert "Brand1 MPN1" in result
    assert "Supplier1" in result
    assert "€50.0" in result


def test_handle_offer_select_invalid():
    """Test handle_offer_select with invalid label."""
    from app.ui_handlers_cart import handle_offer_select

    mapping = {123: {"brand": "Brand1", "mpn": "MPN1"}}

    # Test with None
    result = handle_offer_select(None, mapping)
    assert "Seleziona un'offerta" in result

    # Test with invalid format
    result = handle_offer_select("invalid", mapping)
    assert "Seleziona un'offerta" in result


def test_handle_cart_add():
    """Test handle_cart_add adds offer to cart."""
    from app.ui_handlers_cart import handle_cart_add

    mapping = {
        123: {"brand": "Brand1", "mpn": "MPN1", "supplier": "Supplier1", "price": 50.0},
    }
    cart = {}

    rows, updated_cart, labels, selected_label, totals = handle_cart_add(
        "123 · Brand1 MPN1", 2, mapping, cart
    )

    # Verify cart updated
    assert 123 in updated_cart
    assert updated_cart[123]["qty"] == 2
    assert updated_cart[123]["brand"] == "Brand1"

    # Verify rows
    assert len(rows) == 1
    assert rows[0][0] == 123  # ID
    assert rows[0][5] == 2  # qty

    # Verify labels
    assert len(labels) == 1
    assert labels[0] == "123 · Brand1 MPN1"

    # Verify selected label is the newly added item
    assert selected_label == "123 · Brand1 MPN1"

    # Verify totals string is not empty
    assert totals != ""


def test_handle_cart_add_increments_quantity():
    """Test handle_cart_add increments quantity if item already in cart."""
    from app.ui_handlers_cart import handle_cart_add

    mapping = {
        123: {"brand": "Brand1", "mpn": "MPN1", "supplier": "Supplier1", "price": 50.0},
    }
    cart = {
        123: {
            "brand": "Brand1",
            "mpn": "MPN1",
            "supplier": "Supplier1",
            "price": 50.0,
            "qty": 1,
        },
    }

    rows, updated_cart, labels, selected_label, totals = handle_cart_add(
        "123 · Brand1 MPN1", 2, mapping, cart
    )

    # Verify quantity incremented (1 + 2 = 3)
    assert updated_cart[123]["qty"] == 3


def test_handle_cart_remove():
    """Test handle_cart_remove removes offer from cart."""
    from app.ui_handlers_cart import handle_cart_remove

    cart = {
        123: {
            "brand": "Brand1",
            "mpn": "MPN1",
            "supplier": "Supplier1",
            "price": 50.0,
            "qty": 2,
        },
        456: {
            "brand": "Brand2",
            "mpn": "MPN2",
            "supplier": "Supplier2",
            "price": 75.0,
            "qty": 1,
        },
    }

    rows, updated_cart, labels, totals = handle_cart_remove("123 · Brand1 MPN1", cart)

    # Verify item removed
    assert 123 not in updated_cart
    assert 456 in updated_cart

    # Verify rows only show remaining item
    assert len(rows) == 1
    assert rows[0][0] == 456

    # Verify labels
    assert len(labels) == 1
    assert "456" in labels[0]


def test_handle_cart_clear():
    """Test handle_cart_clear empties the cart."""
    from app.ui_handlers_cart import handle_cart_clear

    rows, cart, labels, totals = handle_cart_clear()

    assert rows == []
    assert cart == {}
    assert labels == []
    assert totals == ""


def test_handle_cart_adjust_increment():
    """Test handle_cart_adjust increments quantity."""
    from app.ui_handlers_cart import handle_cart_adjust

    cart = {
        123: {
            "brand": "Brand1",
            "mpn": "MPN1",
            "supplier": "Supplier1",
            "price": 50.0,
            "qty": 2,
        },
    }

    rows, updated_cart, labels, selected_label, totals = handle_cart_adjust(
        "+", "123 · Brand1 MPN1", cart
    )

    # Verify quantity incremented
    assert updated_cart[123]["qty"] == 3

    # Verify rows reflect new quantity
    assert rows[0][5] == 3  # qty column

    # Verify selected label preserved
    assert selected_label == "123 · Brand1 MPN1"


def test_handle_cart_adjust_decrement():
    """Test handle_cart_adjust decrements quantity (minimum 1)."""
    from app.ui_handlers_cart import handle_cart_adjust

    cart = {
        123: {
            "brand": "Brand1",
            "mpn": "MPN1",
            "supplier": "Supplier1",
            "price": 50.0,
            "qty": 2,
        },
    }

    rows, updated_cart, labels, selected_label, totals = handle_cart_adjust(
        "-", "123 · Brand1 MPN1", cart
    )

    # Verify quantity decremented
    assert updated_cart[123]["qty"] == 1

    # Verify rows reflect new quantity
    assert rows[0][5] == 1  # qty column


def test_handle_cart_adjust_decrement_minimum():
    """Test handle_cart_adjust does not decrement below 1."""
    from app.ui_handlers_cart import handle_cart_adjust

    cart = {
        123: {
            "brand": "Brand1",
            "mpn": "MPN1",
            "supplier": "Supplier1",
            "price": 50.0,
            "qty": 1,
        },
    }

    rows, updated_cart, labels, selected_label, totals = handle_cart_adjust(
        "-", "123 · Brand1 MPN1", cart
    )

    # Verify quantity stays at 1
    assert updated_cart[123]["qty"] == 1
