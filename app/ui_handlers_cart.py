"""Business logic for cart UI handlers - separated from Gradio UI concerns."""

from __future__ import annotations

import os
from typing import Any

from .logging_utils import log_exception


def parse_offer_id_from_label(label: str | None) -> int | None:
    """
    Extract offer ID from label format: "{id} · {brand} {mpn} · ...".

    Returns:
        Offer ID as integer, or None if parsing fails
    """
    if not label:
        return None
    try:
        return int(str(label).split(" · ")[0])
    except (ValueError, IndexError):
        return None


def build_cart_rows(
    cart: dict[int, dict[str, Any]],
) -> tuple[list[list[Any]], list[str]]:
    """
    Build cart table rows and dropdown labels from cart state.

    Args:
        cart: Dict mapping offer_id to offer details (brand, mpn, supplier, price, qty)

    Returns:
        Tuple of (table_rows, dropdown_labels)
        - table_rows: List of rows for Gradio Dataframe [id, brand, mpn, supplier, price, qty, total]
        - dropdown_labels: List of labels for cart selection dropdown
    """
    rows = []
    labels = []
    for oid, info in cart.items():
        qty = int(info.get("qty", 1))
        price = float(info.get("price", 0.0))
        total = price * qty
        rows.append(
            [
                oid,
                info.get("brand", ""),
                info.get("mpn", ""),
                info.get("supplier", ""),
                round(price, 2),
                qty,
                round(total, 2),
            ]
        )
        labels.append(f"{oid} · {info.get('brand', '')} {info.get('mpn', '')}")
    return rows, labels


def calculate_cart_totals(
    cart: dict[int, dict[str, Any]],
) -> tuple[float, float, float, float]:
    """
    Calculate cart financial totals with VAT.

    Args:
        cart: Dict mapping offer_id to offer details with price and qty

    Returns:
        Tuple of (subtotal, vat_rate, vat_amount, total)
    """
    subtotal = 0.0
    for info in cart.values():
        qty = int(info.get("qty", 1))
        price = float(info.get("price", 0.0))
        subtotal += price * qty

    vat_rate = float(os.environ.get("APP_VAT", "0") or 0)
    vat = subtotal * vat_rate
    total = subtotal + vat

    return subtotal, vat_rate, vat, total


def format_totals_markdown(cart: dict[int, dict[str, Any]]) -> str:
    """
    Format cart totals as markdown string.

    Args:
        cart: Cart state dict

    Returns:
        Formatted markdown string with subtotal, VAT, and total
    """
    subtotal, vat_rate, vat, total = calculate_cart_totals(cart)
    return f"**Subtotale:** €{subtotal:.2f} &nbsp;&nbsp; **IVA ({vat_rate * 100:.0f}%):** €{vat:.2f} &nbsp;&nbsp; **Totale:** €{total:.2f}"


def handle_offer_select(
    offer_label: str | None, mapping: dict[int, dict[str, Any]]
) -> str:
    """
    Handle offer selection and return preview markdown.

    Args:
        offer_label: Selected offer label from dropdown
        mapping: Dict mapping offer_id to offer details

    Returns:
        Markdown preview string for selected offer
    """
    if not offer_label:
        return "Seleziona un'offerta per i dettagli"

    offer_id = parse_offer_id_from_label(offer_label)
    if offer_id is None:
        log_exception(
            "ui",
            "select-offer",
            "failed to parse offer label",
            ValueError("Invalid label format"),
            extra={"label": offer_label},
        )
        return "Seleziona un'offerta per i dettagli"

    info = mapping.get(offer_id, {})
    return f"**Offerta {offer_id}** — {info.get('brand', '')} {info.get('mpn', '')} — {info.get('supplier', '')} — €{info.get('price', '')}"


def handle_cart_add(
    offer_label: str | None,
    qty: float | int,
    mapping: dict[int, dict[str, Any]],
    cart: dict[int, dict[str, Any]],
) -> tuple[list[list[Any]], dict[int, dict[str, Any]], list[str], str | None, str]:
    """
    Handle adding offer to cart.

    Args:
        offer_label: Selected offer label
        qty: Quantity to add
        mapping: Offer ID to details mapping
        cart: Current cart state

    Returns:
        Tuple of (rows, updated_cart, labels, selected_label, totals_md)
    """
    if not offer_label:
        return [], cart, [], None, format_totals_markdown(cart)

    offer_id = parse_offer_id_from_label(offer_label)
    if offer_id is None:
        log_exception(
            "ui",
            "cart-add",
            "failed to parse offer label",
            ValueError("Invalid label format"),
            extra={"label": offer_label},
        )
        return [], cart, [], None, format_totals_markdown(cart)

    info = mapping.get(offer_id)
    if not info:
        return [], cart, [], None, format_totals_markdown(cart)

    # Get or create cart entry
    prev = cart.get(offer_id, {**info, "qty": 0})
    prev_qty = int(prev.get("qty", 0))
    prev["qty"] = prev_qty + max(1, int(qty))
    cart[offer_id] = prev

    rows, labels = build_cart_rows(cart)
    selected_label = labels[-1] if labels else None

    return rows, cart, labels, selected_label, format_totals_markdown(cart)


def handle_cart_remove(
    cart_label: str | None, cart: dict[int, dict[str, Any]]
) -> tuple[list[list[Any]], dict[int, dict[str, Any]], list[str], str]:
    """
    Handle removing offer from cart.

    Args:
        cart_label: Selected cart item label
        cart: Current cart state

    Returns:
        Tuple of (rows, updated_cart, labels, totals_md)
    """
    if not cart_label:
        return [], cart, [], format_totals_markdown(cart)

    offer_id = parse_offer_id_from_label(cart_label)
    if offer_id is None:
        log_exception(
            "ui",
            "cart-remove",
            "failed to parse cart label",
            ValueError("Invalid label format"),
            extra={"label": cart_label},
        )
        return [], cart, [], format_totals_markdown(cart)

    # Remove from cart
    cart.pop(offer_id, None)

    rows, labels = build_cart_rows(cart)
    return rows, cart, labels, format_totals_markdown(cart)


def handle_cart_clear() -> tuple[
    list[list[Any]], dict[int, dict[str, Any]], list[str], str
]:
    """
    Handle clearing entire cart.

    Returns:
        Tuple of (empty_rows, empty_cart, empty_labels, empty_totals)
    """
    return [], {}, [], ""


def handle_cart_adjust(
    sign: str, cart_label: str | None, cart: dict[int, dict[str, Any]]
) -> tuple[list[list[Any]], dict[int, dict[str, Any]], list[str], str | None, str]:
    """
    Handle adjusting cart item quantity (+/-).

    Args:
        sign: "+" to increment, "-" to decrement
        cart_label: Selected cart item label
        cart: Current cart state

    Returns:
        Tuple of (rows, updated_cart, labels, selected_label, totals_md)
    """
    if not cart_label:
        return [], cart, [], None, format_totals_markdown(cart)

    offer_id = parse_offer_id_from_label(cart_label)
    if offer_id is None:
        log_exception(
            "ui",
            "cart-adjust",
            "failed to parse cart label",
            ValueError("Invalid label format"),
            extra={"label": cart_label},
        )
        return [], cart, [], None, format_totals_markdown(cart)

    if offer_id not in cart:
        return [], cart, [], None, format_totals_markdown(cart)

    # Adjust quantity
    cur = cart[offer_id]
    qty = int(cur.get("qty", 1))
    if sign == "+":
        qty += 1
    else:
        qty = max(1, qty - 1)
    cur["qty"] = qty
    cart[offer_id] = cur

    rows, labels = build_cart_rows(cart)
    return rows, cart, labels, cart_label, format_totals_markdown(cart)
