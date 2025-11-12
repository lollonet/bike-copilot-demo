from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ..types import OfferInput, ProductInput


def parse_unified_csv(
    path: Path, mapping_yaml: Path
) -> tuple[list[ProductInput], list[OfferInput]]:
    mapping: dict[str, Any] = (
        yaml.safe_load(mapping_yaml.read_text(encoding="utf-8")) or {}
    )
    supplier: str = mapping.get("supplier", "CSVProvider")
    delimiter: str = mapping.get("delimiter", ",")
    cols: dict[str, str] = mapping.get("columns", {})
    defaults: dict[str, Any] = mapping.get("defaults", {})

    required = {"mpn", "name", "price"}
    if not required.issubset(set(cols.keys())):
        missing = required - set(cols.keys())
        raise ValueError(f"mapping YAML missing columns for: {sorted(missing)}")

    df = pd.read_csv(
        path, sep=delimiter, dtype=str, engine="python", skip_blank_lines=True, header=0
    )
    # Drop rows that are entirely empty like ';;;;'
    df = df.dropna(how="all")
    # If header row wasn't detected (e.g., file starts with delimiter-only row),
    # detect if first data row contains our expected column names and promote it to header.
    expected_headers = set(v for v in cols.values() if v)
    if not expected_headers.issubset(set(df.columns)) and len(df) > 0:
        first = [str(x).strip() for x in list(df.iloc[0].values)]
        if expected_headers.issubset(set(first)):
            df.columns = first
            df = df.iloc[1:]
            df = df.reset_index(drop=True)

    def get_val(row: dict[str, Any], key: str) -> str | None:
        col = cols.get(key)
        if not col:
            return None
        v = row.get(col)
        if v is None:
            return None
        s = str(v).strip()
        return s if s != "" else None

    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    for r in df.to_dict(orient="records"):
        category = get_val(r, "category") or get_val(r, "categoria")
        brand = (
            get_val(r, "brand")
            or mapping.get("brand_default")
            or (category or "Generic")
        )
        mpn = get_val(r, "mpn") or ""
        name = get_val(r, "name") or f"{brand} {mpn}".strip()
        price_raw = get_val(r, "price") or ""
        # normalize price: handle comma decimal
        price_s = price_raw.replace("€", "").replace(" ", "")
        if "," in price_s and "." not in price_s:
            price_s = price_s.replace(",", ".")
        try:
            price = float(price_s)
        except ValueError:
            continue

        products.append(
            ProductInput(
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
        )
        in_stock = bool(defaults.get("in_stock", True))
        lead = defaults.get("lead_time_days")
        # Optional dealer-specific code column
        dealer_code_col = cols.get("dealer_code") or cols.get("sku")
        dealer_code = (str(r.get(dealer_code_col)).strip() if dealer_code_col and r.get(dealer_code_col) is not None else None)
        offers.append(
            OfferInput(
                brand=brand,
                mpn=mpn,
                supplier=supplier,
                price=price,
                in_stock=in_stock,
                lead_time_days=int(lead)
                if isinstance(lead, (int, str)) and str(lead).isdigit()
                else None,
                extra={"dealer_pn": dealer_code} if dealer_code else {},
            )
        )

    return products, offers
