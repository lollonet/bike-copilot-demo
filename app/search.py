from __future__ import annotations


import yaml
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .config import settings
from .models import EventLog, Product, SessionLocal, SupplierOffer
from .types import OfferItem, SearchRequest, SearchResponse, FacetsResponse


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
    synonyms = _load_synonyms()
    with SessionLocal() as db:
        products = db.scalars(
            select(Product).options(selectinload(Product.offers))
        ).all()
    filtered: list[Product] = []
    qtext = (request.query_text or "").strip().lower()
    tokens = [t for t in qtext.split() if t]
    for p in products:
        ok = True
        if tokens:
            hay = f"{p.brand or ''} {p.mpn or ''} {p.name or ''}".lower()
            for t in tokens:
                if t not in hay:
                    ok = False
                    break
        if request.category and (p.category or "") != request.category:
            ok = False
        if request.speed and apply_synonyms(
            request.speed, "speed", synonyms
        ) != apply_synonyms(p.speed, "speed", synonyms):
            ok = False
        if request.freehub and apply_synonyms(
            request.freehub.value, "freehub", synonyms
        ) != apply_synonyms(p.freehub, "freehub", synonyms):
            ok = False
        if request.brake and apply_synonyms(
            request.brake.value, "brake", synonyms
        ) != apply_synonyms(p.brake, "brake", synonyms):
            ok = False
        if request.axle and apply_synonyms(
            request.axle, "axle", synonyms
        ) != apply_synonyms(p.axle, "axle", synonyms):
            ok = False
        if request.rotor and apply_synonyms(
            request.rotor.value, "rotor", synonyms
        ) != apply_synonyms(p.rotor, "rotor", synonyms):
            ok = False
        if ok:
            filtered.append(p)
    return filtered


def search(request: SearchRequest) -> SearchResponse:
    synonyms = _load_synonyms()
    filtered = _prefilter_products(request)

    # Gather offers
    offers: list[tuple[SupplierOffer, int, list[str], list[str], str, str]] = []
    for p in filtered:
        for o in p.offers:
            comp, pros, cons = compatibility_score(request, p, synonyms)
            offers.append((o, comp, pros, cons, p.brand, p.mpn))

    # Offer-level filters: suppliers, in_stock, budget (0 treated as no limit)
    eff_budget = (
        float(request.budget_max)
        if (request.budget_max is not None and float(request.budget_max) > 0)
        else None
    )
    if request.suppliers and len(request.suppliers) > 0:
        offers = [t for t in offers if t[0].supplier in request.suppliers]
    if request.in_stock_only:
        offers = [t for t in offers if t[0].in_stock]
    if eff_budget is not None:
        offers = [
            t
            for t in offers
            if (t[0].price is not None and float(t[0].price) <= eff_budget)
        ]

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


def facets(request: SearchRequest) -> FacetsResponse:
    synonyms = _load_synonyms()
    filtered = _prefilter_products(request)
    counts = {
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

    def _canon_category(value: str | None) -> str | None:
        if value is None:
            return None
        t = " ".join(str(value).strip().split())
        if not t:
            return None
        # Title-case generic labels; keep common acronyms uppercased
        cap = t.title()
        for ac in ("MTB", "BMX", "E-BIKE", "Ebike", "CX"):
            cap = cap.replace(ac.title(), ac)
        return cap

    for p in filtered:
        # Category facet
        if p.category:
            keyc = _canon_category(p.category)
            if keyc is None:
                keyc = str(p.category)
            counts["category"][keyc] = counts["category"].get(keyc, 0) + 1

        # Product-level facet counts (canonicalized)
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
        # Offer-level data for price range
        for o in p.offers:
            # Apply supplier/in_stock filters for offer-level facets
            if request.in_stock_only and not o.in_stock:
                continue
            if (
                request.suppliers
                and len(request.suppliers) > 0
                and o.supplier not in request.suppliers
            ):
                continue
            if o.price is not None:
                if eff_budget is None or float(o.price) <= eff_budget:
                    prices.append(float(o.price))
                    offer_total += 1
            sname = o.supplier
            counts["supplier"][sname] = counts["supplier"].get(sname, 0) + 1

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


def dry_run() -> None:
    req = SearchRequest(query_text=None, speed=None)
    res = search(req)
    for it in res.items:
        print(it.model_dump())
