from __future__ import annotations

from pathlib import Path
from typing import Any

import pdfplumber
import pandas as pd
import yaml

from ..types import OfferInput, ProductInput


def _load_mapping(mapping_yaml: Path | None) -> dict[str, Any]:
    if mapping_yaml and mapping_yaml.exists():
        return yaml.safe_load(mapping_yaml.read_text(encoding="utf-8")) or {}
    return {}


def _extract_tables_from_pdf(path: Path) -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for tbl in tables:
                if not tbl or not tbl[0]:
                    continue
                cols = [str(c) if c is not None else "" for c in tbl[0]]
                df = pd.DataFrame(tbl[1:], columns=pd.Index(cols))
                frames.append(df)
    return frames


def _normalize_dataframe(
    frames: list[pd.DataFrame], header_map: dict[str, str]
) -> pd.DataFrame | None:
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    df.columns = [str(c).strip() for c in df.columns]
    if header_map:
        rename_map = {k: v for k, v in header_map.items() if k in df.columns}
        if rename_map:
            df = df.rename(columns=rename_map)
    return df


def _to_bool(val: Any) -> bool:
    s = str(val).strip().lower()
    return s in {"1", "y", "yes", "true", "x", "stock", "available"}


def _to_int(val: Any) -> int | None:
    text = str(val).strip()
    if not text:
        return None
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return None


def _row_to_product(
    row: dict[str, Any],
    brand_c: str,
    mpn_c: str,
    name_c: str,
) -> ProductInput | None:
    brand = str(row.get(brand_c, "")).strip()
    mpn = str(row.get(mpn_c, "")).strip()
    name = str(row.get(name_c, "")).strip()
    if not brand or not mpn:
        return None
    return ProductInput(
        brand=brand,
        mpn=mpn,
        ean=None,
        name=name or f"{brand} {mpn}",
        speed=None,
        brake=None,
        axle=None,
        rotor=None,
        freehub=None,
    )


def _row_price(row: dict[str, Any], price_c: str) -> float | None:
    price_val = row.get(price_c)
    text = str(price_val).replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _row_to_offer(
    row: dict[str, Any],
    product: ProductInput,
    price_c: str,
    supplier_name: str,
    stock_c: str | None,
    lead_c: str | None,
) -> OfferInput | None:
    price = _row_price(row, price_c)
    if price is None:
        return None
    in_stock = _to_bool(row.get(stock_c)) if stock_c else True
    lead = _to_int(row.get(lead_c)) if lead_c else None
    return OfferInput(
        brand=product.brand,
        mpn=product.mpn,
        supplier=supplier_name,
        price=price,
        in_stock=in_stock,
        lead_time_days=lead,
    )


def extract_from_pdf(
    path: Path, mapping_yaml: Path | None = None
) -> tuple[list[ProductInput], list[OfferInput]]:
    mapping = _load_mapping(mapping_yaml)
    header_map: dict[str, str] = mapping.get("columns", {})
    frames = _extract_tables_from_pdf(path)
    df = _normalize_dataframe(frames, header_map)
    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    if df is None:
        return products, offers

    _populate_from_dataframe(df, mapping, products, offers)
    return products, offers


def _populate_from_dataframe(
    df: pd.DataFrame,
    mapping: dict[str, Any],
    products: list[ProductInput],
    offers: list[OfferInput],
) -> None:
    brand_c = mapping.get("brand_col", "brand")
    mpn_c = mapping.get("mpn_col", "mpn")
    name_c = mapping.get("name_col", "name")
    price_c = mapping.get("price_col", "price")
    supplier_name = mapping.get("supplier", "PDFProvider")
    stock_c = mapping.get("stock_col")
    lead_c = mapping.get("lead_col")

    for row in df.to_dict(orient="records"):
        product = _row_to_product(row, brand_c, mpn_c, name_c)
        if product is None:
            continue
        offer = _row_to_offer(
            row,
            product,
            price_c=price_c,
            supplier_name=supplier_name,
            stock_c=stock_c,
            lead_c=lead_c,
        )
        if offer is None:
            continue
        products.append(product)
        offers.append(offer)
