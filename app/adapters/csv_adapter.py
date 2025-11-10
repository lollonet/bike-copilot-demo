from __future__ import annotations

from pathlib import Path
import math

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


def parse_products_csv(path: Path) -> list[ProductInput]:
    df = pd.read_csv(path)
    required = {"brand", "mpn", "name"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"products.csv missing columns: {sorted(missing)}")
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
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"offers.csv missing columns: {sorted(missing)}")
    rows: list[OfferInput] = []
    for r in df.to_dict(orient="records"):
        in_stock_raw = r.get("in_stock")
        if isinstance(in_stock_raw, str):
            in_stock_val = in_stock_raw.strip().lower() in {"1", "true", "yes", "y"}
        else:
            in_stock_val = (
                bool(int(in_stock_raw)) if in_stock_raw is not None else False
            )
        price_val = r.get("price")
        if _is_missing(price_val):
            continue
        lead_val = r.get("lead_time_days")
        lead_str = str(lead_val) if not _is_missing(lead_val) else ""
        lead = int(lead_str) if lead_str.isdigit() else None
        rows.append(
            OfferInput(
                brand=str(r.get("brand", "")).strip(),
                mpn=str(r.get("mpn", "")).strip(),
                supplier=str(r.get("supplier", "")).strip(),
                price=float(str(price_val)),
                in_stock=in_stock_val,
                lead_time_days=lead,
            )
        )
    return rows
