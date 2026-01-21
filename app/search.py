from __future__ import annotations


import os
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .logging_utils import log_event
from .models import EventLog, Product, SupplierOffer
from .types import FacetsResponse, OfferItem, SearchRequest, SearchResponse


_category_synonyms_cache: dict[str, str] = {}


def _build_category_synonym_mapping(raw: object) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if isinstance(raw, dict):
        for canon, aliases in raw.items():
            mapping[str(canon).lower().strip()] = str(canon)
            for alias in aliases or []:
                mapping[str(alias).lower().strip()] = str(canon)
    elif raw not in ({}, None):
        log_event(
            "WARN",
            op="category_synonyms",
            kind="search",
            message="category synonyms file has unexpected structure; using empty map",
            trace_id=None,
            extra={"type": type(raw).__name__},
        )
    return mapping


def _load_category_synonyms() -> dict[str, str]:
    global _category_synonyms_cache
    if _category_synonyms_cache:
        return _category_synonyms_cache
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
    _category_synonyms_cache = _build_category_synonym_mapping(raw)
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
    try:
        with open(settings.synonyms_path, "r", encoding="utf-8") as f:
            data: dict[str, dict[str, list[str]]] = yaml.safe_load(f) or {}
        return data
    except (OSError, FileNotFoundError) as exc:
        log_event(
            "WARN",
            op="synonyms",
            kind="load",
            message="failed to load synonyms file, search quality degraded",
            extra={"path": str(settings.synonyms_path), "error": str(exc)},
        )
        return {}


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
    price_norm = (
        (min_price / offer.price)
        if (offer.price and offer.price > 0 and min_price)
        else 0.5
    )
    avail = 1.0 if offer.in_stock else 0.0
    lead_days = offer.lead_time_days if offer.lead_time_days is not None else 7
    lead = 1.0 / (1.0 + float(lead_days))
    comp = comp_score / 5.0
    return 0.35 * avail + 0.25 * comp + 0.20 * lead + 0.20 * price_norm


def _prefilter_products(request: SearchRequest, db: Session) -> list[Product]:
    """Load all products and apply text/attribute filters at product level."""
    synonyms = _load_synonyms()
    products = db.scalars(select(Product).options(selectinload(Product.offers))).all()
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


def _effective_budget_max(budget_max: float | None) -> float | None:
    if budget_max is None:
        return None
    value = float(budget_max)
    if value <= 0:
        return None
    return value


def _log_search_event(
    db: Session, request: SearchRequest, items: list[OfferItem]
) -> None:
    db.add(
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
    db.commit()


def search(request: SearchRequest, db: Session | None = None) -> SearchResponse:
    synonyms = _load_synonyms()
    if db is None:
        from .models import SessionLocal

        with SessionLocal() as scoped_db:
            return search(request, scoped_db)
    filtered = _prefilter_products(request, db)
    offers = _gather_scored_offers(request, filtered, synonyms)
    if not offers:
        return SearchResponse(items=[])
    items = _build_search_items(offers)
    _log_search_event(db, request, items)
    return SearchResponse(items=items)


def _build_search_items(
    offers: list[tuple[SupplierOffer, int, list[str], list[str], str, str]],
) -> list[OfferItem]:
    min_price = min(
        o.price for (o, _c, _p, _cn, _b, _m) in offers if o.price is not None
    )
    ranked = sorted(
        offers, key=lambda t: final_score(t[0], t[1], min_price), reverse=True
    )
    top3 = ranked[:3]
    return [
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


def _offer_passes_filters_for_search(
    offer: SupplierOffer,
    allowed_suppliers: set[str] | None,
    in_stock_only: bool,
    eff_budget: float | None,
) -> bool:
    if allowed_suppliers is not None and offer.supplier not in allowed_suppliers:
        return False
    if in_stock_only and not offer.in_stock:
        return False
    if eff_budget is not None:
        if offer.price is None:
            return False
        if float(offer.price) > eff_budget:
            return False
    return True


def _gather_scored_offers(
    request: SearchRequest,
    products: list[Product],
    synonyms: dict[str, dict[str, list[str]]],
) -> list[tuple[SupplierOffer, int, list[str], list[str], str, str]]:
    """Collect offers with compatibility score and apply offer-level filters."""
    offers: list[tuple[SupplierOffer, int, list[str], list[str], str, str]] = []
    eff_budget = _effective_budget_max(request.budget_max)
    allowed_suppliers: set[str] | None = (
        set(request.suppliers) if request.suppliers else None
    )
    in_stock_only = bool(request.in_stock_only)
    for p in products:
        comp, pros, cons = compatibility_score(request, p, synonyms)
        for o in p.offers:
            if not _offer_passes_filters_for_search(
                o, allowed_suppliers, in_stock_only, eff_budget
            ):
                continue
            offers.append((o, comp, pros, cons, p.brand, p.mpn))
    return offers


def facets(request: SearchRequest, db: Session | None = None) -> FacetsResponse:
    synonyms = _load_synonyms()
    if db is None:
        from .models import SessionLocal

        with SessionLocal() as scoped_db:
            return facets(request, scoped_db)
    filtered = _prefilter_products(request, db)
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


def _init_facet_counts() -> dict[str, dict[str, int]]:
    return {
        "speed": {},
        "freehub": {},
        "brake": {},
        "axle": {},
        "rotor": {},
        "supplier": {},
        "category": {},
    }


def _bump_facet_count(
    counts: dict[str, dict[str, int]],
    cat: str,
    value: str | None,
    synonyms: dict[str, dict[str, list[str]]],
) -> None:
    if value is None:
        return
    canon = apply_synonyms(value, cat, synonyms)
    if canon is None:
        return
    bucket = counts[cat]
    key = str(canon)
    bucket[key] = bucket.get(key, 0) + 1


def _bump_category_count(
    counts: dict[str, dict[str, int]],
    product: Product,
) -> None:
    if not product.category:
        return
    keyc = canon_category(product.category)
    if keyc is None:
        keyc = str(product.category)
    bucket = counts["category"]
    bucket[keyc] = bucket.get(keyc, 0) + 1


def _should_include_offer_in_supplier_counts(
    offer: SupplierOffer,
    allowed_suppliers: set[str] | None,
    in_stock_only: bool,
) -> bool:
    if in_stock_only and not offer.in_stock:
        return False
    if allowed_suppliers is not None and offer.supplier not in allowed_suppliers:
        return False
    return True


def _accumulate_offer_facets_for_product(
    counts: dict[str, dict[str, int]],
    prices: list[float],
    request: SearchRequest,
    product: Product,
    eff_budget: float | None,
    allowed_suppliers: set[str] | None,
    in_stock_only: bool,
) -> int:
    offer_total = 0
    supplier_counts = counts["supplier"]
    for o in product.offers:
        if not _should_include_offer_in_supplier_counts(
            o, allowed_suppliers, in_stock_only
        ):
            continue
        if o.price is not None and (eff_budget is None or float(o.price) <= eff_budget):
            prices.append(float(o.price))
            offer_total += 1
        sname = o.supplier
        supplier_counts[sname] = supplier_counts.get(sname, 0) + 1
    return offer_total


def _facet_filter_context(
    request: SearchRequest,
) -> tuple[float | None, set[str] | None, bool]:
    eff_budget = _effective_budget_max(request.budget_max)
    allowed_suppliers: set[str] | None = (
        set(request.suppliers) if request.suppliers else None
    )
    return eff_budget, allowed_suppliers, bool(request.in_stock_only)


def _compute_facets_for_products(
    request: SearchRequest,
    products: list[Product],
    synonyms: dict[str, dict[str, list[str]]],
) -> tuple[dict[str, dict[str, int]], list[float], int]:
    counts = _init_facet_counts()
    prices: list[float] = []
    offer_total = 0
    eff_budget, allowed_suppliers, in_stock_only = _facet_filter_context(request)

    for p in products:
        _bump_category_count(counts, p)
        _bump_facet_count(counts, "speed", p.speed, synonyms)
        _bump_facet_count(counts, "freehub", p.freehub, synonyms)
        _bump_facet_count(counts, "brake", p.brake, synonyms)
        _bump_facet_count(counts, "axle", p.axle, synonyms)
        _bump_facet_count(counts, "rotor", p.rotor, synonyms)
        offer_total += _accumulate_offer_facets_for_product(
            counts,
            prices,
            request,
            p,
            eff_budget,
            allowed_suppliers,
            in_stock_only,
        )

    return counts, prices, offer_total
