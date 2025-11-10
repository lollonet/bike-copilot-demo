from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Freehub(str, Enum):
    HG = "HG"
    XD = "XD"
    MS = "MS"


class Rotor(str, Enum):
    CL = "CL"
    SIX_BOLT = "6B"


class Brake(str, Enum):
    DISC = "disc"


class Problem(BaseModel):
    kind: str
    message: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    trace_id: str | None = None


class SearchRequest(BaseModel):
    query_text: str | None = None
    speed: str | None = None
    freehub: Freehub | None = None
    brake: Brake | None = None
    axle: str | None = None
    rotor: Rotor | None = None
    budget_max: float | None = None


class OfferItem(BaseModel):
    id: int
    brand: str
    mpn: str
    supplier: str
    price: float
    in_stock: bool
    lead_time_days: int | None = None
    score: float
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    items: list[OfferItem]
    ts: datetime = Field(default_factory=datetime.utcnow)


class QuoteRequest(BaseModel):
    offer_id: int
    customer_name: str
    customer_contact: str
    validity_days: int = 7
    notes: str | None = None


class QuoteResponse(BaseModel):
    content_type: str
    html_path: str
    pdf_path: str | None = None
    file_url: str | None = None


# Internal ingest boundary (provider adapters → ingest orchestrator)
class ProductInput(BaseModel):
    brand: str
    mpn: str
    ean: str | None = None
    name: str
    speed: str | None = None
    brake: str | None = None
    axle: str | None = None
    rotor: str | None = None
    freehub: str | None = None


class OfferInput(BaseModel):
    brand: str
    mpn: str
    supplier: str
    price: float
    in_stock: bool
    lead_time_days: int | None = None
    currency: str | None = None
    extra: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
