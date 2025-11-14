from __future__ import annotations

from datetime import datetime, timezone
from shutil import which

import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from typing import Mapping
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from .config import settings
from .models import EventLog, SessionLocal, SupplierOffer, create_all
from .search import search, facets as compute_facets
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
from .logging_utils import log_event
from .pn import search_pn, search_pn_batch
from .optimizer import optimize


app = FastAPI(title="Bike Copilot Demo")

_basic = HTTPBasic(auto_error=False)


def require_auth(creds: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    # If creds configured, enforce; otherwise allow (demo default)
    if settings.basic_user and settings.basic_pass:
        if not creds or not (
            secrets.compare_digest(creds.username, settings.basic_user)
            and secrets.compare_digest(creds.password, settings.basic_pass)
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        # Auth disabled; do nothing
        return


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
def api_search(req: SearchRequest, request: Request) -> SearchResponse:
    res = search(req)
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
def api_facets(req: SearchRequest, request: Request) -> FacetsResponse:
    res = compute_facets(req)
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
def api_search_pn(req: SearchPNRequest, request: Request) -> SearchPNResponse:
    res = search_pn(req)
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
    req: SearchPNBatchRequest, request: Request
) -> SearchPNBatchResponse:
    res = search_pn_batch(req)
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
def api_dealers() -> DealersResponse:
    create_all()
    with SessionLocal() as db:
        # Fetch per-dealer offers count and max(updated_at)
        from sqlalchemy import func

        rows = (
            db.query(
                SupplierOffer.supplier,
                func.count(SupplierOffer.id),
                func.max(SupplierOffer.updated_at),
            )
            .group_by(SupplierOffer.supplier)
            .all()
        )
    dealers = [
        DealerInfo(name=str(name), offers=int(cnt), last_updated=upd)
        for (name, cnt, upd) in rows
    ]
    return DealersResponse(dealers=dealers)


@app.post("/optimize", response_model=OptimizeResponse)
def api_optimize(req: OptimizeRequest, request: Request) -> OptimizeResponse:
    res = optimize(req)
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
    req: QuoteRequest, request: Request, _: None = Depends(require_auth)
) -> QuoteResponse:
    create_all()
    with SessionLocal() as db:
        # Build items list from request
        if not req.items:
            raise HTTPException(
                status_code=400,
                detail=Problem(
                    kind="invalid_request", message="items required"
                ).model_dump(),
            )
        items: list[dict[str, object]] = []
        for cart in req.items:
            offer = db.scalar(
                select(SupplierOffer).where(SupplierOffer.id == cart.offer_id)
            )
            if not offer:
                raise HTTPException(
                    status_code=400,
                    detail=Problem(
                        kind="not_found", message=f"offer_id {cart.offer_id} not found"
                    ).model_dump(),
                )
            product = offer.product
            qty = max(1, int(cart.qty))
            items.append(
                {
                    "brand": product.brand,
                    "mpn": product.mpn,
                    "name": product.name,
                    "supplier": offer.supplier,
                    "price": offer.price,
                    "qty": qty,
                    "in_stock": offer.in_stock,
                    "lead_time_days": offer.lead_time_days,
                }
            )
        context = {
            "customer_name": req.customer_name,
            "customer_contact": req.customer_contact,
            "validity_days": req.validity_days,
            "notes": req.notes,
            "items": items,
        }
        from .quote import render_quote

        html_path, pdf_path = render_quote(context)

        # Log event
        db.add(
            EventLog(
                type="quote_created",
                payload={"count": len(items), "pdf": bool(pdf_path)},
            )
        )
        db.commit()
        log_event(
            "INFO",
            op="quote",
            kind="api",
            message="quote created",
            trace_id=getattr(request.state, "trace_id", None),
            extra={"count": len(items), "pdf": bool(pdf_path)},
        )
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
def kpi_today(request: Request, _: None = Depends(require_auth)) -> dict[str, int]:
    create_all()
    now = datetime.now(timezone.utc)
    start = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
    with SessionLocal() as db:
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
def kpi_summary(_: Request, __: None = Depends(require_auth)) -> KPISummaryResponse:
    from datetime import datetime, timedelta
    from sqlalchemy import func

    create_all()
    # Use naive UTC consistently to match SQLite naive timestamps
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)
    with SessionLocal() as db:
        # Totali prodotti (via tabella Product)
        from .models import Product

        products_total = int(db.query(func.count(Product.id)).scalar() or 0)
        # prodotti con almeno un'offerta
        prod_with_offers = db.query(SupplierOffer.product_id).distinct().count()
        # Offerte totale e aggiornate nelle 24h
        offers_total = int(db.query(func.count(SupplierOffer.id)).scalar() or 0)
        offers_24h = int(
            db.query(func.count(SupplierOffer.id))
            .filter(SupplierOffer.updated_at >= cutoff)
            .scalar()
            or 0
        )

        # Per-dealer: numero offerte, % aggiornate 24h, lag dal max(updated_at)
        per_dealer: list[KPIDealerEntry] = []
        rows = (
            db.query(
                SupplierOffer.supplier,
                func.count(SupplierOffer.id),
                func.max(SupplierOffer.updated_at),
            )
            .group_by(SupplierOffer.supplier)
            .all()
        )
        for dealer, cnt, last_upd in rows:
            cnt = int(cnt or 0)
            upd_24h = int(
                db.query(func.count(SupplierOffer.id))
                .filter(
                    SupplierOffer.supplier == dealer,
                    SupplierOffer.updated_at >= cutoff,
                )
                .scalar()
                or 0
            )
            pct_24 = (upd_24h / cnt * 100.0) if cnt > 0 else 0.0
            lag_days = None
            if last_upd is not None:
                lu = (
                    last_upd.replace(tzinfo=None)
                    if getattr(last_upd, "tzinfo", None)
                    else last_upd
                )
                lag_days = max(0.0, (now - lu).total_seconds() / 86400.0)
            per_dealer.append(
                KPIDealerEntry(
                    dealer=str(dealer),
                    offers=cnt,
                    updated_24h_pct=round(pct_24, 2),
                    lag_days=round(lag_days, 2) if lag_days is not None else None,
                )
            )

        # PN non mappati: offerte con extra.dealer_pn senza riga PNMapping corrispondente
        # Carichiamo le offerte con dealer_pn e verifichiamo mapping in Python
        from .pn import normalize_pn
        from .models import PNMapping, Product

        cand_offers = (
            db.query(SupplierOffer).filter(SupplierOffer.extra.isnot(None)).all()
        )
        unmapped = 0
        for off in cand_offers:
            try:
                dealer_code = None
                if isinstance(off.extra, dict):
                    dealer_code = off.extra.get("dealer_pn")  # type: ignore[assignment]
                if not dealer_code:
                    continue
                dealer_norm = normalize_pn(str(dealer_code))
                exists = (
                    db.query(PNMapping.id)
                    .filter(
                        PNMapping.dealer == off.supplier,
                        PNMapping.dealer_pn_norm == dealer_norm,
                    )
                    .first()
                )
                if not exists:
                    unmapped += 1
            except Exception:
                continue

    coverage = (
        (prod_with_offers / products_total * 100.0) if products_total > 0 else 0.0
    )
    upd_pct = (offers_24h / offers_total * 100.0) if offers_total > 0 else 0.0
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
