from __future__ import annotations

"""PN-first search utilities.

All comments are in English as per repo policy; UI strings remain Italian.
"""

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import Product, SessionLocal, PNMapping
from .types import (
    PNOfferItem,
    SearchPNRequest,
    SearchPNResponse,
    SearchPNBatchRequest,
    SearchPNBatchResponse,
)


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


def search_pn_batch(req: SearchPNBatchRequest) -> SearchPNBatchResponse:
    """Batch PN search avoiding repeated full-table scans.

    Strategy:
    - Normalize all requested PNs once
    - In a single session:
      - Load Products (+offers) once and build a normalized MPN → products map
      - Load PNMapping rows for any requested normalized PN
      - For each requested PN, union products from direct match and mapping
      - Apply dealers/in_stock filters and sort per PN
    """
    want = [str(x) for x in (req.items or [])]
    # De-duplicate while preserving order
    seen: set[str] = set()
    items: list[str] = []
    for w in want:
        if w not in seen:
            seen.add(w)
            items.append(w)
    targets = [normalize_pn(w) for w in items]
    target_set = set(t for t in targets if t)

    with SessionLocal() as db:
        # Load products once with offers
        products = db.scalars(
            select(Product).options(selectinload(Product.offers))
        ).all()
        # Build helper indexes
        norm_map: dict[str, list[Product]] = {}
        id_index: dict[int, Product] = {}
        for p in products:
            id_index[p.id] = p
            key = normalize_pn(p.mpn)
            if key:
                norm_map.setdefault(key, []).append(p)

        # Load PNMapping rows for requested set
        pid_by_norm: dict[str, set[int]] = {k: set() for k in target_set}
        if target_set:
            rows = db.query(PNMapping.maker_pn_norm, PNMapping.dealer_pn_norm, PNMapping.product_id).filter(
                (PNMapping.maker_pn_norm.in_(list(target_set))) | (PNMapping.dealer_pn_norm.in_(list(target_set)))
            ).all()
            for maker_norm, dealer_norm, pid in rows:
                if maker_norm in pid_by_norm:
                    pid_by_norm[maker_norm].add(int(pid))
                if dealer_norm in pid_by_norm:
                    pid_by_norm[dealer_norm].add(int(pid))

    # Build responses per requested PN (preserve input order)
    results: list[SearchPNResponse] = []
    for original, norm in zip(items, targets):
        prods = list(norm_map.get(norm, []))
        # Keep semantics consistent with single-item search:
        # use PNMapping only as fallback when there is no direct Product match
        if not prods:
            ids_present: set[int] = set()
            for pid in pid_by_norm.get(norm, set()):
                if pid not in ids_present and pid in id_index:
                    prods.append(id_index[pid])
                    ids_present.add(pid)

        # Gather offers and apply filters
        offers = _gather_offers(prods)
        # Filters
        if req.dealers:
            allowed = set(req.dealers)
            offers = [it for it in offers if it.dealer in allowed]
        if req.in_stock_only:
            offers = [it for it in offers if it.in_stock]
        # Sort
        def _key(it: PNOfferItem) -> tuple[int, float, int]:
            instock_rank = 0 if it.in_stock else 1
            price = it.price if it.price is not None else float("inf")
            lead = it.lead_time_days if it.lead_time_days is not None else 9999
            return (instock_rank, price, lead)

        offers_sorted = sorted(offers, key=_key)
        results.append(SearchPNResponse(maker_pn=original, offers=offers_sorted))

    return SearchPNBatchResponse(results=results)
