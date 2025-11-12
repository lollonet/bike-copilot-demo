from __future__ import annotations

"""PN-first search utilities.

All comments are in English as per repo policy; UI strings remain Italian.
"""

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import Product, SessionLocal, PNMapping
from .types import PNOfferItem, SearchPNRequest, SearchPNResponse


def normalize_pn(text: str) -> str:
    """Normalize a part number: uppercase, remove spaces and separators.

    Conservative rule set for v1; alias tables can be added later.
    """
    t = (text or "").strip().upper()
    # Keep only letters and digits
    out = []
    for ch in t:
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def _gather_offers(products: Iterable[Product]) -> list[PNOfferItem]:
    items: list[PNOfferItem] = []
    for p in products:
        for o in p.offers:
            items.append(
                PNOfferItem(
                    offer_id=o.id,
                    dealer=o.supplier,
                    price=float(o.price) if o.price is not None else None,
                    in_stock=bool(o.in_stock),
                    lead_time_days=o.lead_time_days,
                    updated_at=o.updated_at,
                    brand=p.brand,
                    mpn=p.mpn,
                    name=p.name,
                )
            )
    return items


def search_pn(req: SearchPNRequest) -> SearchPNResponse:
    """Search offers by maker PN only using the local DB.

    Strategy v1: equality on normalized Product.mpn.
    Later we can add PNMapping and alias resolution.
    """
    target = normalize_pn(req.maker_pn)
    with SessionLocal() as db:
        # First, try direct product match by normalized maker PN
        products = db.scalars(
            select(Product).options(selectinload(Product.offers))
        ).all()
        matches = [p for p in products if normalize_pn(p.mpn) == target]
        # If no direct match, consult PNMapping using either maker or dealer normalized PN
        if not matches:
            pids: set[int] = set()
            rows = db.scalars(
                select(PNMapping.product_id).where(
                    (PNMapping.maker_pn_norm == target) | (PNMapping.dealer_pn_norm == target)
                )
            ).all()
            pids.update(int(pid) for pid in rows)
            if pids:
                matches = [p for p in products if p.id in pids]
        offers = _gather_offers(matches)

    # Filters
    if req.dealers:
        allowed = set(req.dealers)
        offers = [it for it in offers if it.dealer in allowed]
    if req.in_stock_only:
        offers = [it for it in offers if it.in_stock]

    # Sort: in-stock first, then by price asc (None last), then lead time asc
    def _key(it: PNOfferItem) -> tuple[int, float, int]:
        instock_rank = 0 if it.in_stock else 1
        price = it.price if it.price is not None else float("inf")
        lead = it.lead_time_days if it.lead_time_days is not None else 9999
        return (instock_rank, price, lead)

    offers_sorted = sorted(offers, key=_key)
    return SearchPNResponse(maker_pn=req.maker_pn, offers=offers_sorted)
