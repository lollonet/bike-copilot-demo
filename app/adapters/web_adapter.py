from __future__ import annotations

from pathlib import Path
from typing import NotRequired, TypedDict

from bs4 import BeautifulSoup
import yaml

from ..types import OfferInput, ProductInput


class PaginationMapping(TypedDict, total=False):
    next: str  # CSS selector for the "next page" link


class SearchMapping(TypedDict, total=False):
    url_template: str  # e.g. https://shop.example/search?q={q}


class WebMapping(TypedDict):
    supplier: str
    root: str
    brand: str
    mpn: str
    name: str
    price: str
    in_stock: NotRequired[str]
    lead_time_days: NotRequired[str]
    pagination: NotRequired[PaginationMapping]
    search: NotRequired[SearchMapping]


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


def fetch_and_parse_urls(
    urls: list[str],
    mapping_yaml: Path,
    follow_next: bool = False,
    max_pages: int = 1,
    delay_sec: float = 0.0,
    headers: dict[str, str] | None = None,
) -> tuple[list[ProductInput], list[OfferInput]]:
    """Fetch one or more URLs and parse them using the provided mapping.

    - If follow_next is True and mapping.pagination.next is set, follows next links up to max_pages.
    - headers can include cookies/auth; keep polite delays via delay_sec.
    """
    import httpx
    import time

    mapping = _load_mapping(mapping_yaml)
    all_products: list[ProductInput] = []
    all_offers: list[OfferInput] = []
    seen_pages: set[str] = set()

    def _fetch(u: str) -> str:
        with httpx.Client(
            timeout=10.0, headers=headers or {"User-Agent": "BikeCopilotBot/0.1"}
        ) as client:
            r = client.get(u)
            r.raise_for_status()
            return r.text

    for seed in urls:
        if seed in seen_pages:
            continue
        seen_pages.add(seed)
        try:
            html = _fetch(seed)
        except Exception:
            continue
        p, o = parse_html(html, mapping)
        all_products.extend(p)
        all_offers.extend(o)

        if (
            follow_next
            and "pagination" in mapping
            and isinstance(mapping["pagination"], dict)
        ):
            next_sel = mapping["pagination"].get("next")  # type: ignore[index]
            if next_sel:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html, "html.parser")
                page_count = 1
                nxt = soup.select_one(next_sel)
                while nxt is not None and page_count < max_pages:
                    href = nxt.get("href") if nxt else None
                    if not href or href in seen_pages:
                        break
                    seen_pages.add(href)
                    time.sleep(max(0.0, delay_sec))
                    try:
                        html = _fetch(href)
                    except Exception:
                        break
                    p2, o2 = parse_html(html, mapping)
                    all_products.extend(p2)
                    all_offers.extend(o2)
                    soup = BeautifulSoup(html, "html.parser")
                    nxt = soup.select_one(next_sel)
                    page_count += 1

    return all_products, all_offers


def build_search_urls(query: str, mapping_yaml: Path) -> list[str]:
    mapping = _load_mapping(mapping_yaml)
    s = mapping.get("search")
    if not s or ("url_template" not in s):
        raise ValueError("mapping.search.url_template is required for search-web")
    tmpl = s.get("url_template", "")
    from urllib.parse import quote_plus

    return [tmpl.format(q=quote_plus(query))]
