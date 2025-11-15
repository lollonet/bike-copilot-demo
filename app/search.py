from __future__ import annotations


import yaml
import os
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .config import settings
from .logging_utils import log_event
from .models import EventLog, Product, SessionLocal, SupplierOffer
from .types import FacetsResponse, OfferItem, SearchRequest, SearchResponse


_category_synonyms_cache: dict[str, str] = {}


def _load_category_synonyms() -> dict[str, str]:
    global _category_synonyms_cache
    if _category_synonyms_cache:
        return _category_synonyms_cache
    mapping: dict[str, str] = {}
    raw: object = {}
    try:
        if os.path.exists(settings.category_synonyms_path):
            with open(settings.category_synonyms_path, "r", encoding="utf-8") as cf:
                raw = yaml.safe_load(cf) or {}
    except (OSError, yaml.YAMLError) as exc:
        log_event(
            "WARN",
            op="category_synonyms",
            kind="search",
            message="failed to load category synonyms; using empty map",
            trace_id=None,
            extra={"error": str(exc)},
        )
        raw = {}
    if isinstance(raw, dict):
        for canon, aliases in raw.items():
            mapping[str(canon).lower().strip()] = str(canon)
            for a in aliases or []:
                mapping[str(a).lower().strip()] = str(canon)
    elif raw not in ({}, None):
        log_event(
            "WARN",
            op="category_synonyms",
            kind="search",
            message="category synonyms file has unexpected structure; using empty map",
            trace_id=None,
            extra={"type": type(raw).__name__},
        )
    _category_synonyms_cache = mapping
    return _category_synonyms_cache


def canon_category(value: str | None) -> str | None:
    """Canonicalize category labels using synonyms map and stable casing."""
    if value is None:
        return None
    t = " ".join(str(value).strip().split())
    if not t:
        return None
    low = t.lower()
    syn = _load_category_synonyms()
    if low in syn:
        return syn[low]
    cap = t.title()
    for ac in ("MTB", "BMX", "E-BIKE", "Ebike", "CX"):
        cap = cap.replace(ac.title(), ac)
    return cap


def _load_synonyms() -> dict[str, dict[str, list[str]]]:
    with open(settings.synonyms_path, "r", encoding="utf-8") as f:
        data: dict[str, dict[str, list[str]]] = yaml.safe_load(f) or {}
    return data


def apply_synonyms(
    value: str | None, category: str, synonyms: dict[str, dict[str, list[str]]]
) -> str | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    cat = synonyms.get(category, {})
    for canon, alts in cat.items():
        all_vals = [canon.lower()] + [a.lower() for a in alts]
        if v in all_vals:
            return canon
    return value


def compatibility_score(
    req: SearchRequest, product: Product, synonyms: dict[str, dict[str, list[str]]]
) -> tuple[int, list[str], list[str]]:
    score = 0
    pros: list[str] = []
    cons: list[str] = []

    def match(cat: str, req_val: str | None, prod_val: str | None) -> None:
        nonlocal score
        r = apply_synonyms(req_val, cat, synonyms)
        p = apply_synonyms(prod_val, cat, synonyms)
        if r is None:
            return
        if r == p:
            score += 1
            pros.append(f"{cat} match: {r}")
        else:
            cons.append(f"{cat} mismatch: requested {r}, product {p}")

    match("speed", req.speed, product.speed)
    match("freehub", req.freehub.value if req.freehub else None, product.freehub)
    match("brake", req.brake.value if req.brake else None, product.brake)
    match("axle", req.axle, product.axle)
    match("rotor", req.rotor.value if req.rotor else None, product.rotor)
    return score, pros, cons


def final_score(offer: SupplierOffer, comp_score: int, min_price: float) -> float:
    price_norm = (min_price / offer.price) if (offer.price and min_price) else 0.5
    avail = 1.0 if offer.in_stock else 0.0
    lead_days = offer.lead_time_days if offer.lead_time_days is not None else 7
    lead = 1.0 / (1.0 + float(lead_days))
    comp = comp_score / 5.0
    return 0.35 * avail + 0.25 * comp + 0.20 * lead + 0.20 * price_norm


def _prefilter_products(request: SearchRequest) -> list[Product]:
    """Load all products and apply text/attribute filters at product level."""
    synonyms = _load_synonyms()
    with SessionLocal() as db:
        products = db.scalars(
            select(Product).options(selectinload(Product.offers))
        ).all()
    qtext = (request.query_text or "").strip().lower()
    tokens = [t for t in qtext.split() if t]
    filtered: list[Product] = []
    for p in products:
        if not _match_product_text(p, tokens):
            continue
        if not _match_product_category(request, p):
            continue
        if not _match_product_tech(request, p, synonyms):
            continue
        filtered.append(p)
    return filtered


def _match_product_text(product: Product, tokens: list[str]) -> bool:
    if not tokens:
        return True
    hay = f"{product.brand or ''} {product.mpn or ''} {product.name or ''}".lower()
    return all(t in hay for t in tokens)


def _match_product_category(req: SearchRequest, product: Product) -> bool:
    if not req.category:
        return True
    return canon_category(product.category) == canon_category(req.category)


def _match_product_tech(
    req: SearchRequest, product: Product, synonyms: dict[str, dict[str, list[str]]]
) -> bool:
    def norm(cat: str, val: str | None) -> str | None:
        return apply_synonyms(val, cat, synonyms)

    if req.speed and norm("speed", req.speed) != norm("speed", product.speed):
        return False
    if req.freehub and norm("freehub", req.freehub.value) != norm(
        "freehub", product.freehub
    ):
        return False
    if req.brake and norm("brake", req.brake.value) != norm("brake", product.brake):
        return False
    if req.axle and norm("axle", req.axle) != norm("axle", product.axle):
        return False
    if req.rotor and norm("rotor", req.rotor.value) != norm("rotor", product.rotor):
        return False
    return True


def search(request: SearchRequest) -> SearchResponse:
    synonyms = _load_synonyms()
    filtered = _prefilter_products(request)
    offers = _gather_scored_offers(request, filtered, synonyms)

    if not offers:
        return SearchResponse(items=[])

    min_price = min(
        o.price for (o, _c, _p, _cn, _b, _m) in offers if o.price is not None
    )
    ranked = sorted(
        offers, key=lambda t: final_score(t[0], t[1], min_price), reverse=True
    )
    top3 = ranked[:3]
    items = [
        OfferItem(
            id=o.id,
            brand=brand,
            mpn=mpn,
            supplier=o.supplier,
            price=float(o.price),
            in_stock=bool(o.in_stock),
            lead_time_days=o.lead_time_days,
            score=final_score(o, comp, min_price),
            pros=pros,
            cons=cons,
        )
        for (o, comp, pros, cons, brand, mpn) in top3
    ]
    # Log event
    with SessionLocal() as log_db:
        log_db.add(
            EventLog(
                type="search",
                payload={
                    "filters": {
                        "speed": request.speed,
                        "freehub": request.freehub.value if request.freehub else None,
                        "brake": request.brake.value if request.brake else None,
                        "axle": request.axle,
                        "rotor": request.rotor.value if request.rotor else None,
                        "budget_max": request.budget_max,
                    },
                    "results": len(items),
                },
            )
        )
        log_db.commit()
    return SearchResponse(items=items)


def _gather_scored_offers(
    request: SearchRequest,
    products: list[Product],
    synonyms: dict[str, dict[str, list[str]]],
) -> list[tuple[SupplierOffer, int, list[str], list[str], str, str]]:
    """Collect offers with compatibility score and apply offer-level filters."""
    offers: list[tuple[SupplierOffer, int, list[str], list[str], str, str]] = []
    for p in products:
        for o in p.offers:
            comp, pros, cons = compatibility_score(request, p, synonyms)
            offers.append((o, comp, pros, cons, p.brand, p.mpn))

    eff_budget = (
        float(request.budget_max)
        if (request.budget_max is not None and float(request.budget_max) > 0)
        else None
    )
    if request.suppliers:
        allowed_sup = set(request.suppliers)
        offers = [t for t in offers if t[0].supplier in allowed_sup]
    if request.in_stock_only:
        offers = [t for t in offers if t[0].in_stock]
    if eff_budget is not None:
        offers = [
            t
            for t in offers
            if (t[0].price is not None and float(t[0].price) <= eff_budget)
        ]
    return offers


def facets(request: SearchRequest) -> FacetsResponse:
    synonyms = _load_synonyms()
    filtered = _prefilter_products(request)
    counts, prices, offer_total = _compute_facets_for_products(
        request, filtered, synonyms
    )
    price_info = {
        "min": (min(prices) if prices else None),
        "max": (max(prices) if prices else None),
    }
    return FacetsResponse(
        speed=counts["speed"],
        freehub=counts["freehub"],
        brake=counts["brake"],
        axle=counts["axle"],
        rotor=counts["rotor"],
        supplier=counts["supplier"],
        category=counts["category"],
        price=price_info,
        totals={"products": len(filtered), "offers": offer_total},
    )


def _compute_facets_for_products(
    request: SearchRequest,
    products: list[Product],
    synonyms: dict[str, dict[str, list[str]]],
) -> tuple[dict[str, dict[str, int]], list[float], int]:
    counts: dict[str, dict[str, int]] = {
        "speed": {},
        "freehub": {},
        "brake": {},
        "axle": {},
        "rotor": {},
        "supplier": {},
        "category": {},
    }
    prices: list[float] = []
    offer_total = 0
    eff_budget = (
        float(request.budget_max)
        if (request.budget_max is not None and float(request.budget_max) > 0)
        else None
    )

    for p in products:
        if p.category:
            keyc = canon_category(p.category)
            if keyc is None:
                keyc = str(p.category)
            counts["category"][keyc] = counts["category"].get(keyc, 0) + 1

        def bump(cat: str, value: str | None) -> None:
            if value is None:
                return
            canon = apply_synonyms(value, cat, synonyms)
            if canon is None:
                return
            d = counts[cat]
            key = str(canon)
            d[key] = d.get(key, 0) + 1

        bump("speed", p.speed)
        bump("freehub", p.freehub)
        bump("brake", p.brake)
        bump("axle", p.axle)
        bump("rotor", p.rotor)

        for o in p.offers:
            if request.in_stock_only and not o.in_stock:
                continue
            if request.suppliers and o.supplier not in set(request.suppliers):
                continue
            if o.price is not None:
                if eff_budget is None or float(o.price) <= eff_budget:
                    prices.append(float(o.price))
                    offer_total += 1
            sname = o.supplier
            counts["supplier"][sname] = counts["supplier"].get(sname, 0) + 1

    return counts, prices, offer_total
