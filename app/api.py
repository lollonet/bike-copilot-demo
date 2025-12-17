from __future__ import annotations

from datetime import datetime, timezone, timedelta
from shutil import which

import os
import secrets
from typing import Mapping

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .config import settings
from .deps import SessionDep
from .models import (
    EventLog,
    SupplierOffer,
    Product,
    PNMapping,
    create_all,
)
from .optimizer import optimize
from .search import facets as compute_facets
from .search import search
from .types import (
    Problem,
    QuoteRequest,
    QuoteResponse,
    SearchRequest,
    SearchResponse,
    FacetsResponse,
    SearchPNRequest,
    SearchPNResponse,
    SearchPNBatchRequest,
    SearchPNBatchResponse,
    DealerInfo,
    DealersResponse,
    OptimizeRequest,
    OptimizeResponse,
    KPISummaryResponse,
    KPIDealerEntry,
)
from .logging_utils import log_event, log_exception
from .pn import search_pn, search_pn_batch, normalize_pn


app = FastAPI(title="Bike Copilot Demo")

_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    # If creds configured, enforce; otherwise allow (demo default)
    basic_user = os.environ.get("APP_BASIC_USER", settings.basic_user)
    basic_pass = os.environ.get("APP_BASIC_PASS", settings.basic_pass)
    if basic_user and basic_pass:
        if not creds or not (
            secrets.compare_digest(creds.username, basic_user)
            and secrets.compare_digest(creds.password, basic_pass)
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")


@app.middleware("http")
async def attach_trace_id(request: Request, call_next):
    import uuid

    trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.get("/health")
def health(request: Request) -> Mapping[str, object]:
    # Ensure DB exists and report environment
    create_all()
    db_ok = True
    pdfkit_ok = bool(which("wkhtmltopdf"))
    from . import __version__

    payload = {"status": "ok", "db": db_ok, "pdfkit": pdfkit_ok, "version": __version__}
    log_event(
        "INFO",
        op="health",
        kind="status",
        message="health ok",
        trace_id=getattr(request.state, "trace_id", None),
    )
    return payload


@app.post("/search", response_model=SearchResponse, responses={400: {"model": Problem}})
def api_search(req: SearchRequest, request: Request, db: SessionDep) -> SearchResponse:
    res = search(req, db)
    log_event(
        "INFO",
        op="search",
        kind="api",
        message="search completed",
        trace_id=getattr(request.state, "trace_id", None),
        extra={"results": len(res.items)},
    )
    return res


@app.post("/facets", response_model=FacetsResponse, responses={400: {"model": Problem}})
def api_facets(req: SearchRequest, request: Request, db: SessionDep) -> FacetsResponse:
    res = compute_facets(req, db)
    log_event(
        "INFO",
        op="facets",
        kind="api",
        message="facets computed",
        trace_id=getattr(request.state, "trace_id", None),
        extra={
            "products": res.totals.get("products", 0),
            "offers": res.totals.get("offers", 0),
        },
    )
    return res


@app.post(
    "/search_pn", response_model=SearchPNResponse, responses={400: {"model": Problem}}
)
def api_search_pn(
    req: SearchPNRequest, request: Request, db: SessionDep
) -> SearchPNResponse:
    res = search_pn(req, db)
    log_event(
        "INFO",
        op="search_pn",
        kind="api",
        message="search_pn completed",
        trace_id=getattr(request.state, "trace_id", None),
        extra={"offers": len(res.offers)},
    )
    return res


@app.post(
    "/search_pn_batch",
    response_model=SearchPNBatchResponse,
    responses={400: {"model": Problem}},
)
def api_search_pn_batch(
    req: SearchPNBatchRequest, request: Request, db: SessionDep
) -> SearchPNBatchResponse:
    res = search_pn_batch(req, db)
    log_event(
        "INFO",
        op="search_pn_batch",
        kind="api",
        message="batch completed",
        trace_id=getattr(request.state, "trace_id", None),
        extra={"requested": len(req.items or []), "results": len(res.results)},
    )
    return res


@app.get("/dealers", response_model=DealersResponse)
def api_dealers(db: SessionDep) -> DealersResponse:
    create_all()
    rows = db.execute(
        select(
            SupplierOffer.supplier,
            func.count(SupplierOffer.id),
            func.max(SupplierOffer.updated_at),
        ).group_by(SupplierOffer.supplier)
    ).all()
    dealers = [
        DealerInfo(name=str(name), offers=int(cnt), last_updated=upd)
        for (name, cnt, upd) in rows
    ]
    return DealersResponse(dealers=dealers)


@app.post("/optimize", response_model=OptimizeResponse)
def api_optimize(
    req: OptimizeRequest, request: Request, db: SessionDep
) -> OptimizeResponse:
    res = optimize(req, db=db)
    log_event(
        "INFO",
        op="optimize",
        kind="api",
        message="optimize computed",
        trace_id=getattr(request.state, "trace_id", None),
        extra={
            "dealers": len(res.dealers),
            "lines": len(res.lines),
            "total": res.costs.total,
        },
    )
    return res


@app.get("/files/{name:path}")
def serve_file(name: str, _: None = Depends(require_auth)) -> FileResponse:
    # Only serve .html or .pdf from the out directory; prevent traversal.
    from pathlib import Path

    allowed = {".html", ".pdf"}
    p = Path(settings.out_dir) / name
    if not p.is_file() or p.suffix.lower() not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.head("/files/{name:path}")
def head_file(name: str, _: None = Depends(require_auth)) -> Response:
    from pathlib import Path

    allowed = {".html", ".pdf"}
    p = Path(settings.out_dir) / name
    if not p.is_file() or p.suffix.lower() not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(status_code=200)


@app.post("/quote", response_model=QuoteResponse, responses={400: {"model": Problem}})
def api_quote(
    req: QuoteRequest,
    request: Request,
    db: SessionDep,
    _: None = Depends(require_auth),
) -> QuoteResponse:
    create_all()
    items = _quote_items_from_request(db, req)
    response = _render_and_log_quote(db, request, req, items)
    return response


def _quote_items_from_request(
    db: Session, req: QuoteRequest
) -> list[dict[str, object]]:
    carts = _validated_cart_items(req)
    items: list[dict[str, object]] = []
    for cart in carts:
        items.append(_quote_item_from_cart(db, cart))
    return items


def _validated_cart_items(req: QuoteRequest) -> list[QuoteRequest.CartItem]:
    if not req.items:
        raise HTTPException(
            status_code=400,
            detail=Problem(
                kind="invalid_request", message="items required"
            ).model_dump(),
        )
    return req.items


def _quote_item_from_cart(
    db: Session, cart: QuoteRequest.CartItem
) -> dict[str, object]:
    offer = db.scalar(select(SupplierOffer).where(SupplierOffer.id == cart.offer_id))
    if not offer:
        raise HTTPException(
            status_code=400,
            detail=Problem(
                kind="not_found", message=f"offer_id {cart.offer_id} not found"
            ).model_dump(),
        )
    product = offer.product
    qty = max(1, int(cart.qty))
    return {
        "brand": product.brand,
        "mpn": product.mpn,
        "name": product.name,
        "supplier": offer.supplier,
        "price": offer.price,
        "qty": qty,
        "in_stock": offer.in_stock,
        "lead_time_days": offer.lead_time_days,
    }


def _render_and_log_quote(
    db: Session,
    request: Request,
    req: QuoteRequest,
    items: list[dict[str, object]],
) -> QuoteResponse:
    context = _quote_context(req, items)
    html_path, pdf_path = _render_quote_with_context(context)
    _persist_quote_event(db, items, pdf_path)
    _log_quote_created(request, items, pdf_path)
    return _build_quote_response(request, html_path, pdf_path)


def _quote_context(
    req: QuoteRequest, items: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "customer_name": req.customer_name,
        "customer_contact": req.customer_contact,
        "validity_days": req.validity_days,
        "notes": req.notes,
        "items": items,
    }


def _render_quote_with_context(context: dict[str, object]) -> tuple[str, str | None]:
    from .quote import render_quote

    return render_quote(context)


def _persist_quote_event(
    db: Session, items: list[dict[str, object]], pdf_path: str | None
) -> None:
    db.add(
        EventLog(
            type="quote_created",
            payload={"count": len(items), "pdf": bool(pdf_path)},
        )
    )
    db.commit()


def _log_quote_created(
    request: Request, items: list[dict[str, object]], pdf_path: str | None
) -> None:
    log_event(
        "INFO",
        op="quote",
        kind="api",
        message="quote created",
        trace_id=getattr(request.state, "trace_id", None),
        extra={"count": len(items), "pdf": bool(pdf_path)},
    )


def _build_quote_response(
    request: Request, html_path: str, pdf_path: str | None
) -> QuoteResponse:
    from urllib.parse import urljoin
    from pathlib import Path

    file_url = urljoin(str(request.base_url), f"files/{Path(html_path).name}")
    return QuoteResponse(
        content_type="application/pdf" if pdf_path else "text/html",
        html_path=html_path,
        pdf_path=pdf_path,
        file_url=file_url,
    )


@app.get("/kpi/today")
def kpi_today(
    request: Request, db: SessionDep, _: None = Depends(require_auth)
) -> dict[str, int]:
    create_all()
    now = datetime.now(timezone.utc)
    start = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
    rows = db.scalars(select(EventLog.type).where(EventLog.ts >= start)).all()
    counts: dict[str, int] = {}
    for t in rows:
        counts[t] = counts.get(t, 0) + 1
    log_event(
        "INFO",
        op="kpi",
        kind="api",
        message="kpi today",
        trace_id=getattr(request.state, "trace_id", None),
        extra={"counts": counts},
    )
    return counts


@app.get("/kpi/summary", response_model=KPISummaryResponse)
def kpi_summary(
    _: Request, db: SessionDep, __: None = Depends(require_auth)
) -> KPISummaryResponse:
    create_all()
    # Use naive UTC consistently to match SQLite naive timestamps
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)
    (
        products_total,
        prod_with_offers,
        offers_total,
        offers_24h,
    ) = _compute_kpi_totals(db, cutoff)
    per_dealer = _compute_kpi_per_dealer(db, now, cutoff)
    unmapped = _count_unmapped_pn(db)

    coverage = _kpi_coverage_pct(products_total, prod_with_offers)
    upd_pct = _kpi_update_pct(offers_total, offers_24h)
    return KPISummaryResponse(
        products_total=int(products_total),
        products_with_offers=int(prod_with_offers),
        coverage_pn_pct=round(coverage, 2),
        offers_total=offers_total,
        offers_updated_24h=offers_24h,
        updated_24h_pct=round(upd_pct, 2),
        pn_unmapped=int(unmapped),
        per_dealer=per_dealer,
    )


def _compute_kpi_totals(db: Session, cutoff: datetime) -> tuple[int, int, int, int]:
    products_total = int(db.scalar(select(func.count(Product.id))) or 0)
    products_with_offers = int(
        db.scalar(select(func.count(func.distinct(SupplierOffer.product_id)))) or 0
    )
    offers_total = int(db.scalar(select(func.count(SupplierOffer.id))) or 0)
    offers_24h = int(
        db.scalar(
            select(func.count(SupplierOffer.id)).where(
                SupplierOffer.updated_at >= cutoff
            )
        )
        or 0
    )
    return products_total, products_with_offers, offers_total, offers_24h


def _compute_kpi_per_dealer(
    db: Session, now: datetime, cutoff: datetime
) -> list[KPIDealerEntry]:
    per_dealer: list[KPIDealerEntry] = []
    rows = _dealer_aggregation_rows(db)
    for dealer, offers_count, last_updated in rows:
        per_dealer.append(
            _kpi_dealer_entry(db, now, cutoff, dealer, offers_count, last_updated)
        )
    return per_dealer


def _dealer_aggregation_rows(
    db: Session,
) -> list[tuple[str, int, datetime | None]]:
    rows = db.execute(
        select(
            SupplierOffer.supplier,
            func.count(SupplierOffer.id),
            func.max(SupplierOffer.updated_at),
        ).group_by(SupplierOffer.supplier)
    ).all()
    result: list[tuple[str, int, datetime | None]] = []
    for dealer, cnt, last_upd in rows:
        result.append((str(dealer), int(cnt or 0), last_upd))
    return result


def _kpi_dealer_entry(
    db: Session,
    now: datetime,
    cutoff: datetime,
    dealer: str,
    offers_count: int,
    last_updated: datetime | None,
) -> KPIDealerEntry:
    updated_24h = _offers_updated_24h_for_dealer(db, dealer, cutoff)
    pct_24 = (updated_24h / offers_count * 100.0) if offers_count > 0 else 0.0
    lag_days = _dealer_lag_days(now, last_updated)
    return KPIDealerEntry(
        dealer=dealer,
        offers=offers_count,
        updated_24h_pct=round(pct_24, 2),
        lag_days=round(lag_days, 2) if lag_days is not None else None,
    )


def _offers_updated_24h_for_dealer(db: Session, dealer: str, cutoff: datetime) -> int:
    return int(
        db.scalar(
            select(func.count(SupplierOffer.id)).where(
                SupplierOffer.supplier == dealer,
                SupplierOffer.updated_at >= cutoff,
            )
        )
        or 0
    )


def _dealer_lag_days(now: datetime, last_updated: datetime | None) -> float | None:
    if last_updated is None:
        return None
    last_update = (
        last_updated.replace(tzinfo=None)
        if getattr(last_updated, "tzinfo", None)
        else last_updated
    )
    return max(0.0, (now - last_update).total_seconds() / 86400.0)


def _count_unmapped_pn(db: Session) -> int:
    # PN non mappati: offerte con extra.dealer_pn senza riga PNMapping corrispondente
    candidates = db.scalars(
        select(SupplierOffer).where(SupplierOffer.extra.isnot(None))
    ).all()
    unmapped = 0
    for offer in candidates:
        try:
            dealer_code = _dealer_pn_from_offer(offer)
            if not dealer_code:
                continue
            dealer_norm = normalize_pn(dealer_code)
            exists = db.scalar(
                select(PNMapping.id).where(
                    PNMapping.dealer == offer.supplier,
                    PNMapping.dealer_pn_norm == dealer_norm,
                )
            )
            if not exists:
                unmapped += 1
        except Exception as exc:
            log_exception("kpi", "pn-mapping", "failed to compute unmapped dealer PN", exc)
            continue
    return unmapped


def _dealer_pn_from_offer(offer: SupplierOffer) -> str | None:
    extra = offer.extra
    if not isinstance(extra, dict):
        return None
    value = extra.get("dealer_pn")
    if value is None:
        return None
    return str(value)


def _kpi_coverage_pct(products_total: int, products_with_offers: int) -> float:
    if products_total <= 0:
        return 0.0
    return products_with_offers / products_total * 100.0


def _kpi_update_pct(offers_total: int, offers_24h: int) -> float:
    if offers_total <= 0:
        return 0.0
    return offers_24h / offers_total * 100.0
