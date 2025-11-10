from __future__ import annotations

from datetime import datetime, timezone

import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import EventLog, SessionLocal, SupplierOffer, create_all
from .quote import render_quote
from .search import search
from .types import Problem, QuoteRequest, QuoteResponse, SearchRequest, SearchResponse


app = FastAPI(title="Bike Copilot Demo")

_basic = HTTPBasic()


def require_auth(creds: HTTPBasicCredentials = Depends(_basic)) -> None:
    # If creds configured, enforce; otherwise allow (demo default)
    if settings.basic_user and settings.basic_pass:
        if not (secrets.compare_digest(creds.username, settings.basic_user) and secrets.compare_digest(creds.password, settings.basic_pass)):
            raise HTTPException(status_code=401, detail="Unauthorized")
    else:
        # Auth disabled; do nothing
        return


@app.get("/health")
def health() -> dict[str, str]:
    # Ensure DB exists
    create_all()
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse, responses={400: {"model": Problem}})
def api_search(req: SearchRequest) -> SearchResponse:
    return search(req)


# Static files for quotes
app.mount("/files", StaticFiles(directory=settings.out_dir), name="files")


@app.post("/quote", response_model=QuoteResponse, responses={400: {"model": Problem}})
def api_quote(req: QuoteRequest, _: None = Depends(require_auth)) -> QuoteResponse:
    create_all()
    with SessionLocal() as db:  # type: Session
        offer = db.scalar(select(SupplierOffer).where(SupplierOffer.id == req.offer_id))
        if not offer:
            raise HTTPException(status_code=400, detail=Problem(kind="not_found", message="offer_id not found").model_dump())
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
        return QuoteResponse(
            content_type="application/pdf" if pdf_path else "text/html",
            html_path=html_path,
            pdf_path=pdf_path,
        )


@app.get("/kpi/today")
def kpi_today(_: None = Depends(require_auth)) -> dict[str, int]:
    create_all()
    now = datetime.now(timezone.utc)
    start = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
    with SessionLocal() as db:  # type: Session
        rows = db.scalars(select(EventLog.type).where(EventLog.ts >= start)).all()
        counts: dict[str, int] = {}
        for t in rows:
            counts[t] = counts.get(t, 0) + 1
        return counts
