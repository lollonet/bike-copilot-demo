"""Business logic for quote UI handlers - separated from Gradio UI concerns."""

from __future__ import annotations

from typing import Any

from .api_client import api_post_silent
from .logging_utils import log_exception
from .models import SessionLocal
from .quote import render_quote
from .ui_handlers_cart import parse_offer_id_from_label


def render_local_quote(
    items: list[dict[str, int]],
    customer: str,
    contact: str,
    validity: int,
    notes: str,
) -> tuple[str, str, str]:
    """
    Render quote locally using database and template system.

    This is a fallback when the API is unavailable. It queries the database
    for offer details and renders the quote using the local template system.

    Args:
        items: List of dicts with offer_id and qty
        customer: Customer name
        contact: Customer contact info
        validity: Quote validity in days
        notes: Optional notes for the quote

    Returns:
        Tuple of (html_path, pdf_path, empty_file_url)
    """
    from .models import SupplierOffer

    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        for entry in items:
            oid = int(entry.get("offer_id", 0))
            qty = int(entry.get("qty", 1))
            offer = db.get(SupplierOffer, oid)
            if not offer:
                continue
            p = offer.product
            rows.append(
                {
                    "brand": p.brand,
                    "mpn": p.mpn,
                    "name": p.name,
                    "supplier": offer.supplier,
                    "price": offer.price,
                    "qty": qty,
                    "in_stock": offer.in_stock,
                    "lead_time_days": offer.lead_time_days,
                }
            )

    if not rows:
        return "Nessun elemento nel carrello", "", ""

    ctx = {
        "customer_name": customer,
        "customer_contact": contact,
        "validity_days": validity,
        "notes": notes,
        "items": rows,
    }

    html_path, pdf_path = render_quote(ctx)
    return html_path, (pdf_path or ""), ""


def handle_quote_request(
    offer_label: str | None,
    customer: str,
    contact: str,
    validity: int,
    notes: str,
    cart: dict[int, dict[str, Any]],
) -> tuple[str, str, str]:
    """
    Handle quote generation request.

    Business logic that:
    1. Extracts items from cart or selected offer
    2. Tries to generate quote via API
    3. Falls back to local rendering on API failure

    Args:
        offer_label: Selected offer label (fallback if cart is empty)
        customer: Customer name
        contact: Customer contact info
        validity: Quote validity in days
        notes: Optional notes
        cart: Current cart state

    Returns:
        Tuple of (html_path, pdf_path, file_url)
    """
    # Prefer cart items if present; otherwise fallback to selected offer
    items: list[dict[str, Any]] = []

    if cart:
        # Use cart items
        for oid, info in cart.items():
            items.append({"offer_id": int(oid), "qty": int(info.get("qty", 1))})
    else:
        # Fallback to single selected offer
        if not offer_label:
            return "Seleziona un'offerta", "", ""

        offer_id = parse_offer_id_from_label(offer_label)
        if offer_id is None:
            log_exception(
                "ui",
                "quote",
                "failed to parse offer label",
                ValueError("Invalid label format"),
                extra={"label": offer_label},
            )
            return "Seleziona un'offerta", "", ""

        items = [{"offer_id": offer_id, "qty": 1}]

    # Try API first
    try:
        payload = {
            "items": items,
            "customer_name": customer,
            "customer_contact": contact,
            "validity_days": int(validity),
            "notes": notes or None,
        }
        r = api_post_silent("/quote", payload, timeout=15)

        if r.status_code == 200:
            data = r.json()
            return (
                data.get("html_path", ""),
                data.get("pdf_path") or "",
                data.get("file_url") or "",
            )

        # Fall back to local rendering on non-200
        return render_local_quote(items, customer, contact, validity, notes)

    except Exception as exc:
        log_exception("ui", "quote", "failed to create quote", exc)
        # Robust fallback to local rendering
        return render_local_quote(items, customer, contact, validity, notes)
