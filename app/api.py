from __future__ import annotations

from datetime import datetime, timezone
from shutil import which

import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from typing import Mapping
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse
from sqlalchemy import select

from .config import settings
from .models import EventLog, SessionLocal, SupplierOffer, create_all
from .quote import render_quote
from .search import search
from .types import Problem, QuoteRequest, QuoteResponse, SearchRequest, SearchResponse
from .logging_utils import log_event


app = FastAPI(title="Bike Copilot Demo")

_basic = HTTPBasic()


def require_auth(creds: HTTPBasicCredentials = Depends(_basic)) -> None:
    # If creds configured, enforce; otherwise allow (demo default)
    if settings.basic_user and settings.basic_pass:
        if not (
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


@app.get("/files/{name:path}")
def serve_file(name: str, _: None = Depends(require_auth)) -> FileResponse:
    # Only serve .html or .pdf from the out directory; prevent traversal.
    from pathlib import Path

    allowed = {".html", ".pdf"}
    p = Path(settings.out_dir) / name
    if not p.is_file() or p.suffix.lower() not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(p))


@app.post("/quote", response_model=QuoteResponse, responses={400: {"model": Problem}})
def api_quote(
    req: QuoteRequest, request: Request, _: None = Depends(require_auth)
) -> QuoteResponse:
    create_all()
    with SessionLocal() as db:
        offer = db.scalar(select(SupplierOffer).where(SupplierOffer.id == req.offer_id))
        if not offer:
            raise HTTPException(
                status_code=400,
                detail=Problem(
                    kind="not_found", message="offer_id not found"
                ).model_dump(),
            )
        product = offer.product
        context = {
            "customer_name": req.customer_name,
            "customer_contact": req.customer_contact,
            "validity_days": req.validity_days,
            "notes": req.notes,
            "item": {
                "brand": product.brand,
                "mpn": product.mpn,
                "name": product.name,
                "supplier": offer.supplier,
                "price": offer.price,
                "in_stock": offer.in_stock,
                "lead_time_days": offer.lead_time_days,
            },
        }
        html_path, pdf_path = render_quote(context)

        # Log event
        db.add(
            EventLog(
                type="quote_created",
                payload={
                    "offer_id": offer.id,
                    "brand": product.brand,
                    "mpn": product.mpn,
                    "supplier": offer.supplier,
                    "price": offer.price,
                    "pdf": bool(pdf_path),
                },
            )
        )
        db.commit()
        log_event(
            "INFO",
            op="quote",
            kind="api",
            message="quote created",
            trace_id=getattr(request.state, "trace_id", None),
            extra={"offer_id": offer.id, "pdf": bool(pdf_path)},
        )
        return QuoteResponse(
            content_type="application/pdf" if pdf_path else "text/html",
            html_path=html_path,
            pdf_path=pdf_path,
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
