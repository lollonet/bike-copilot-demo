from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
import pandas as pd
import yaml

from ..types import OfferInput, ProductInput


def extract_from_pdf(path: Path, mapping_yaml: Path | None = None) -> tuple[list[ProductInput], list[OfferInput]]:
    mapping: dict[str, Any] = {}
    if mapping_yaml and mapping_yaml.exists():
        mapping = yaml.safe_load(mapping_yaml.read_text(encoding="utf-8")) or {}

    header_map: dict[str, str] = mapping.get("columns", {})
    products: list[ProductInput] = []
    offers: list[OfferInput] = []

    frames: list[pd.DataFrame] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tbls = page.extract_tables() or []
            for tbl in tbls:
                if not tbl or not tbl[0]:
                    continue
                df = pd.DataFrame(tbl[1:], columns=tbl[0])
                frames.append(df)

    if not frames:
        return products, offers

    df = pd.concat(frames, ignore_index=True)
    # Normalize column names
    df.columns = [str(c).strip() for c in df.columns]
    if header_map:
        df = df.rename(columns={k: v for k, v in header_map.items() if k in df.columns})

    # Required fields for offers
    brand_c = mapping.get("brand_col", "brand")
    mpn_c = mapping.get("mpn_col", "mpn")
    name_c = mapping.get("name_col", "name")
    price_c = mapping.get("price_col", "price")
    supplier_name = mapping.get("supplier", "PDFProvider")
    stock_c = mapping.get("stock_col", None)
    lead_c = mapping.get("lead_col", None)

    # Coerce fields
    def _to_bool(val: Any) -> bool:
        s = str(val).strip().lower()
        return s in {"1", "y", "yes", "true", "x", "stock", "available"}

    def _to_int(val: Any) -> int | None:
        try:
            return int(str(val).strip())
        except Exception:
            return None

    for r in df.to_dict(orient="records"):
        brand = str(r.get(brand_c, "")).strip()
        mpn = str(r.get(mpn_c, "")).strip()
        name = str(r.get(name_c, "")).strip()
        if not brand or not mpn:
            continue
        # Product row
        products.append(
            ProductInput(brand=brand, mpn=mpn, ean=None, name=name or f"{brand} {mpn}", speed=None, brake=None, axle=None, rotor=None, freehub=None)
        )
        # Offer row
        price_val = r.get(price_c)
        try:
            price = float(str(price_val).replace(",", "."))
        except Exception:
            continue
        in_stock = _to_bool(r.get(stock_c)) if stock_c else True
        lead = _to_int(r.get(lead_c)) if lead_c else None
        offers.append(
            OfferInput(
                brand=brand,
                mpn=mpn,
                supplier=supplier_name,
                price=price,
                in_stock=in_stock,
                lead_time_days=lead,
            )
        )

    return products, offers
