from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..types import OfferInput, ProductInput


def parse_products_csv(path: Path) -> list[ProductInput]:
    df = pd.read_csv(path)
    required = {"brand", "mpn", "name"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"products.csv missing columns: {sorted(missing)}")
    rows: list[ProductInput] = []
    for r in df.to_dict(orient="records"):
        rows.append(
            ProductInput(
                brand=str(r.get("brand", "")).strip(),
                mpn=str(r.get("mpn", "")).strip(),
                ean=(str(r["ean"]).strip() if pd.notna(r.get("ean")) else None),
                name=str(r.get("name", "")).strip(),
                speed=(str(r["speed"]).strip() if pd.notna(r.get("speed")) else None),
                brake=(str(r["brake"]).strip() if pd.notna(r.get("brake")) else None),
                axle=(str(r["axle"]).strip() if pd.notna(r.get("axle")) else None),
                rotor=(str(r["rotor"]).strip() if pd.notna(r.get("rotor")) else None),
                freehub=(str(r["freehub"]).strip() if pd.notna(r.get("freehub")) else None),
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
            in_stock_val = bool(int(in_stock_raw)) if in_stock_raw is not None else False
        rows.append(
            OfferInput(
                brand=str(r.get("brand", "")).strip(),
                mpn=str(r.get("mpn", "")).strip(),
                supplier=str(r.get("supplier", "")).strip(),
                price=float(r.get("price")),
                in_stock=in_stock_val,
                lead_time_days=(int(r["lead_time_days"]) if pd.notna(r.get("lead_time_days")) else None),
            )
        )
    return rows

