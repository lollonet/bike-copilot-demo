from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from ..types import OfferInput, ProductInput


def _is_missing(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def _ensure_required_columns(
    df: pd.DataFrame,
    required: set[str],
    label: str,
) -> None:
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"{label} missing columns: {sorted(missing)}")


def _normalized_str_field(row: dict[str, object], key: str) -> str:
    return str(row.get(key, "")).strip()


def parse_products_csv(path: Path) -> list[ProductInput]:
    df = pd.read_csv(path)
    required = {"brand", "mpn", "name"}
    _ensure_required_columns(df, required, "products.csv")
    rows: list[ProductInput] = []
    for r in df.to_dict(orient="records"):
        ean_val = r.get("ean")
        speed_val = r.get("speed")
        brake_val = r.get("brake")
        axle_val = r.get("axle")
        rotor_val = r.get("rotor")
        freehub_val = r.get("freehub")
        rows.append(
            ProductInput(
                brand=str(r.get("brand", "")).strip(),
                mpn=str(r.get("mpn", "")).strip(),
                ean=(str(ean_val).strip() if not _is_missing(ean_val) else None),
                name=str(r.get("name", "")).strip(),
                speed=(str(speed_val).strip() if not _is_missing(speed_val) else None),
                brake=(str(brake_val).strip() if not _is_missing(brake_val) else None),
                axle=(str(axle_val).strip() if not _is_missing(axle_val) else None),
                rotor=(str(rotor_val).strip() if not _is_missing(rotor_val) else None),
                freehub=(
                    str(freehub_val).strip() if not _is_missing(freehub_val) else None
                ),
            )
        )
    return rows


def parse_offers_csv(path: Path) -> list[OfferInput]:
    df = pd.read_csv(path)
    required = {"brand", "mpn", "supplier", "price", "in_stock"}
    rows: list[OfferInput] = []
    _ensure_required_columns(df, required, "offers.csv")
    for record in df.to_dict(orient="records"):
        offer = _offer_from_record(record)
        if offer is not None:
            rows.append(offer)
    return rows


def _offer_from_record(record: dict[str, object]) -> OfferInput | None:
    price_val = record.get("price")
    if _is_missing(price_val):
        return None
    in_stock_val = _parse_in_stock(record.get("in_stock"))
    lead = _parse_lead_time_days(record.get("lead_time_days"))
    return OfferInput(
        brand=_normalized_str_field(record, "brand"),
        mpn=_normalized_str_field(record, "mpn"),
        supplier=_normalized_str_field(record, "supplier"),
        price=float(str(price_val)),
        in_stock=in_stock_val,
        lead_time_days=lead,
    )


def _parse_in_stock(raw: object) -> bool:
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "y"}
    if raw is None:
        return False
    val = _safe_int(raw)
    return bool(val) if val is not None else False


def _parse_lead_time_days(raw: object) -> int | None:
    if _is_missing(raw):
        return None
    try:
        if isinstance(raw, (int, float)):
            return int(raw)
        lead_str = str(raw)
    except (TypeError, ValueError):
        return None
    return int(lead_str) if lead_str.isdigit() else None


def _safe_int(raw: object) -> int | None:
    try:
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, (int, float)):
            return int(raw)
        s = str(raw)
        return int(s) if s.isdigit() else None
    except (TypeError, ValueError):
        return None
