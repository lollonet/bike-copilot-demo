from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict

from bs4 import BeautifulSoup
import yaml

from ..types import OfferInput, ProductInput


class WebMapping(TypedDict):
    supplier: str
    root: str
    brand: str
    mpn: str
    name: str
    price: str
    in_stock: NotRequired[str]
    lead_time_days: NotRequired[str]


def _load_mapping(path: Path) -> WebMapping:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    required = {"supplier", "root", "brand", "mpn", "name", "price"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"mapping YAML missing keys: {sorted(missing)}")
    return WebMapping(**data)


def _text(el) -> str:
    return el.get_text(strip=True) if el is not None else ""


def _to_bool(s: str) -> bool:
    v = s.strip().lower()
    return v in {"1", "yes", "y", "true", "ok", "available", "stock"}


def _to_price(s: str) -> float:
    t = s.strip().replace("€", "").replace(" ", "")
    # handle 12,34 and 12.34
    if "," in t and t.count(",") == 1 and "." not in t:
        t = t.replace(",", ".")
    return float(t)


def parse_html(
    html: str, mapping: WebMapping
) -> tuple[list[ProductInput], list[OfferInput]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(mapping["root"])  # type: ignore[index]
    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    for r in rows:
        brand = _text(r.select_one(mapping["brand"]))
        mpn = _text(r.select_one(mapping["mpn"]))
        name = _text(r.select_one(mapping["name"]))
        price_s = _text(r.select_one(mapping["price"]))
        if not brand or not mpn or not price_s:
            continue
        in_stock = True
        if "in_stock" in mapping:
            in_stock = _to_bool(_text(r.select_one(mapping["in_stock"])) or "")
        lead: int | None = None
        if "lead_time_days" in mapping:
            lead_t = _text(r.select_one(mapping["lead_time_days"]))
            lead = int(lead_t) if lead_t.isdigit() else None

        products.append(
            ProductInput(
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
        )
        offers.append(
            OfferInput(
                brand=brand,
                mpn=mpn,
                supplier=mapping["supplier"],
                price=_to_price(price_s),
                in_stock=in_stock,
                lead_time_days=lead,
            )
        )
    return products, offers


def parse_file(
    html_path: Path, mapping_yaml: Path
) -> tuple[list[ProductInput], list[OfferInput]]:
    mapping = _load_mapping(mapping_yaml)
    html = html_path.read_text(encoding="utf-8")
    return parse_html(html, mapping)
