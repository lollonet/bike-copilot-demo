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
        products = db.scalars(
            select(Product).options(selectinload(Product.offers))
        ).all()
        matches = _match_products_single(target, products, db)
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


def _match_products_single(
    target_norm: str, products: list[Product], db
) -> list[Product]:
    """Locate products for a single normalized PN.

    Strategy: try direct normalized Product.mpn match, then PNMapping fallback.
    """
    direct = [p for p in products if normalize_pn(p.mpn) == target_norm]
    if direct:
        return direct
    pids: set[int] = set()
    rows = db.scalars(
        select(PNMapping.product_id).where(
            (PNMapping.maker_pn_norm == target_norm)
            | (PNMapping.dealer_pn_norm == target_norm)
        )
    ).all()
    for pid in rows:
        pids.add(int(pid))
    if not pids:
        return []
    return [p for p in products if p.id in pids]


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
    # Preserve original order and multiplicity; build a normalized cache
    items: list[str] = [str(x) for x in (req.items or [])]
    targets = [normalize_pn(w) for w in items]
    target_set = set(t for t in targets if t)

    with SessionLocal() as db:
        products = db.scalars(
            select(Product).options(selectinload(Product.offers))
        ).all()
        norm_map, id_index, pid_by_norm = _build_pn_indexes(products, target_set, db)

    results: list[SearchPNResponse] = []
    for original, norm in zip(items, targets):
        prods = _match_products_batch(norm, norm_map, pid_by_norm, id_index)
        offers = _gather_offers(prods)
        offers = _apply_filters(offers, req.dealers, req.in_stock_only)
        offers_sorted = _sort_offers(offers)
        results.append(SearchPNResponse(maker_pn=original, offers=offers_sorted))

    return SearchPNBatchResponse(results=results)


def _build_pn_indexes(
    products: list[Product], target_set: set[str], db
) -> tuple[dict[str, list[Product]], dict[int, Product], dict[str, set[int]]]:
    """Build helper indexes for batch PN search.

    Returns:
    - norm_map: normalized mpn -> products
    - id_index: product id -> product
    - pid_by_norm: normalized PN (maker/dealer) -> product ids
    """
    norm_map: dict[str, list[Product]] = {}
    id_index: dict[int, Product] = {}
    for p in products:
        id_index[p.id] = p
        key = normalize_pn(p.mpn)
        if key:
            norm_map.setdefault(key, []).append(p)

    pid_by_norm: dict[str, set[int]] = {k: set() for k in target_set}
    if target_set:
        rows = (
            db.query(
                PNMapping.maker_pn_norm,
                PNMapping.dealer_pn_norm,
                PNMapping.product_id,
            )
            .filter(
                (PNMapping.maker_pn_norm.in_(list(target_set)))
                | (PNMapping.dealer_pn_norm.in_(list(target_set)))
            )
            .all()
        )
        for maker_norm, dealer_norm, pid in rows:
            value = int(pid)
            if maker_norm in pid_by_norm:
                pid_by_norm[maker_norm].add(value)
            if dealer_norm in pid_by_norm:
                pid_by_norm[dealer_norm].add(value)
    return norm_map, id_index, pid_by_norm


def _match_products_batch(
    norm: str,
    norm_map: dict[str, list[Product]],
    pid_by_norm: dict[str, set[int]],
    id_index: dict[int, Product],
) -> list[Product]:
    """Match products for one PN in batch mode.

    Semantics: identical a search_pn, ma con indici precalcolati.
    """
    prods = list(norm_map.get(norm, []))
    if prods:
        return prods
    ids_present: set[int] = set()
    out: list[Product] = []
    for pid in pid_by_norm.get(norm, set()):
        if pid not in ids_present and pid in id_index:
            out.append(id_index[pid])
            ids_present.add(pid)
    return out


def _apply_filters(
    offers: list[PNOfferItem], dealers: list[str] | None, in_stock_only: bool | None
) -> list[PNOfferItem]:
    filtered = offers
    if dealers:
        allowed = set(dealers)
        filtered = [it for it in filtered if it.dealer in allowed]
    if in_stock_only:
        filtered = [it for it in filtered if it.in_stock]
    return filtered


def _sort_offers(offers: list[PNOfferItem]) -> list[PNOfferItem]:
    def _key(it: PNOfferItem) -> tuple[int, float, int]:
        instock_rank = 0 if it.in_stock else 1
        price = it.price if it.price is not None else float("inf")
        lead = it.lead_time_days if it.lead_time_days is not None else 9999
        return (instock_rank, price, lead)

    return sorted(offers, key=_key)
