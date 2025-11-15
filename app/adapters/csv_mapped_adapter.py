from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ..types import OfferInput, ProductInput


def _load_mapping(mapping_yaml: Path) -> dict[str, Any]:
    return yaml.safe_load(mapping_yaml.read_text(encoding="utf-8")) or {}


def _mapping_columns(mapping: dict[str, Any]) -> dict[str, str]:
    cols: dict[str, str] = mapping.get("columns", {})
    required = {"mpn", "name", "price"}
    if not required.issubset(set(cols.keys())):
        missing = required - set(cols.keys())
        raise ValueError(f"mapping YAML missing columns for: {sorted(missing)}")
    return cols


def _read_catalog_df(path: Path, delimiter: str, cols: dict[str, str]) -> pd.DataFrame:
    df = pd.read_csv(
        path, sep=delimiter, dtype=str, engine="python", skip_blank_lines=True, header=0
    )
    df = df.dropna(how="all")
    expected_headers = {v for v in cols.values() if v}
    if not expected_headers.issubset(set(df.columns)) and len(df) > 0:
        first = [str(x).strip() for x in list(df.iloc[0].values)]
        if expected_headers.issubset(set(first)):
            df.columns = first
            df = df.iloc[1:]
            df = df.reset_index(drop=True)
    return df


def _row_value(row: dict[str, Any], cols: dict[str, str], key: str) -> str | None:
    col = cols.get(key)
    if not col:
        return None
    value = row.get(col)
    if value is None:
        return None
    text = str(value).strip()
    return text if text != "" else None


def _normalize_price(raw: str) -> float | None:
    price_s = raw.replace("€", "").replace(" ", "")
    if "," in price_s and "." not in price_s:
        price_s = price_s.replace(",", ".")
    try:
        return float(price_s)
    except ValueError:
        return None


def _dealer_code(row: dict[str, Any], cols: dict[str, str]) -> str | None:
    dealer_code_col = cols.get("dealer_code") or cols.get("sku")
    if not dealer_code_col:
        return None
    value = row.get(dealer_code_col)
    if value is None:
        return None
    code = str(value).strip()
    return code or None


def _lead_time_days(defaults: dict[str, Any]) -> int | None:
    lead = defaults.get("lead_time_days")
    if isinstance(lead, int):
        return lead
    if isinstance(lead, str) and lead.isdigit():
        return int(lead)
    return None


def _build_product(
    row: dict[str, Any], cols: dict[str, str], mapping: dict[str, Any]
) -> ProductInput | None:
    category = _row_value(row, cols, "category") or _row_value(row, cols, "categoria")
    brand = (
        _row_value(row, cols, "brand")
        or mapping.get("brand_default")
        or (category or "Generic")
    )
    mpn = _row_value(row, cols, "mpn") or ""
    name = _row_value(row, cols, "name") or f"{brand} {mpn}".strip()
    price_raw = _row_value(row, cols, "price") or ""
    price = _normalize_price(price_raw)
    if price is None:
        return None
    return ProductInput(
        brand=brand,
        mpn=mpn,
        ean=None,
        name=name,
        category=category,
        speed=None,
        brake=None,
        axle=None,
        rotor=None,
        freehub=None,
    )


def _build_offer(
    row: dict[str, Any],
    cols: dict[str, str],
    mapping: dict[str, Any],
    defaults: dict[str, Any],
    supplier: str,
) -> OfferInput | None:
    product = _build_product(row, cols, mapping)
    if product is None:
        return None
    in_stock = bool(defaults.get("in_stock", True))
    lead_days = _lead_time_days(defaults)
    dealer_code = _dealer_code(row, cols)
    extra = {"dealer_pn": dealer_code} if dealer_code else {}
    price_raw = _row_value(row, cols, "price") or ""
    price = _normalize_price(price_raw)
    if price is None:
        return None
    return OfferInput(
        brand=product.brand,
        mpn=product.mpn,
        supplier=supplier,
        price=price,
        in_stock=in_stock,
        lead_time_days=lead_days,
        extra=extra,
    )


def parse_unified_csv(
    path: Path, mapping_yaml: Path
) -> tuple[list[ProductInput], list[OfferInput]]:
    mapping = _load_mapping(mapping_yaml)
    supplier: str = mapping.get("supplier", "CSVProvider")
    delimiter: str = mapping.get("delimiter", ",")
    cols = _mapping_columns(mapping)
    defaults: dict[str, Any] = mapping.get("defaults", {})

    df = _read_catalog_df(path, delimiter, cols)

    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    records: list[dict[str, Any]] = df.to_dict(orient="records")
    for row in records:
        product = _build_product(row, cols, mapping)
        if product is None:
            continue
        offer = _build_offer(row, cols, mapping, defaults, supplier)
        if offer is None:
            continue
        products.append(product)
        offers.append(offer)

    return products, offers
