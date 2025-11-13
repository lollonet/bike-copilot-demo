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
    dealer_code: NotRequired[str]
    pagination: NotRequired[PaginationMapping]
    search: NotRequired[SearchMapping]
    item_link: NotRequired[str]
    detail: NotRequired[
        dict[str, str]
    ]  # may include keys: name, price, brand, mpn, in_stock, lead_time_days, category, dealer_code


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
    return v in {
        "1",
        "yes",
        "y",
        "true",
        "ok",
        "available",
        "stock",
        "instock",
        "in stock",
    }


def _to_price(s: str) -> float:
    t = s.strip().replace("€", "").replace(" ", "")
    # handle 12,34 and 12.34
    if "," in t and t.count(",") == 1 and "." not in t:
        t = t.replace(",", ".")
    return float(t)


def _price_text(el) -> str:
    """Extract a single price text from a WooCommerce container.

    Prefer <ins> current price when on sale; else first .woocommerce-Price-amount.
    Fallback to element text.
    """
    if el is None:
        return ""
    # On sale: <ins><span class="woocommerce-Price-amount">€9,90</span></ins>
    ins_amt = el.select_one(
        "ins .woocommerce-Price-amount, ins span.woocommerce-Price-amount"
    )
    if ins_amt is not None:
        return ins_amt.get_text(strip=True)
    amt = el.select_one(".woocommerce-Price-amount, span.amount")
    if amt is not None:
        return amt.get_text(strip=True)
    return el.get_text(strip=True)


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
        price_s = _price_text(r.select_one(mapping["price"]))
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
        # Optional dealer-specific code (SKU) on listing
        dealer_code = None
        if "dealer_code" in mapping:
            dealer_code = _text(r.select_one(mapping["dealer_code"])) or None
        offers.append(
            OfferInput(
                brand=brand,
                mpn=mpn,
                supplier=mapping["supplier"],
                price=_to_price(price_s),
                in_stock=in_stock,
                lead_time_days=lead,
                extra={"dealer_pn": dealer_code} if dealer_code else {},
            )
        )
    return products, offers


def _abs_url(base_url: str, href: str | None) -> str | None:
    if not href:
        return None
    from urllib.parse import urljoin

    return urljoin(base_url, href)


def parse_detail_html(
    html: str, mapping: WebMapping
) -> tuple[ProductInput | None, OfferInput | None]:
    detail = mapping.get("detail") or {}
    soup = BeautifulSoup(html, "html.parser")
    scope = soup
    root_sel = detail.get("root")
    if root_sel:
        root = soup.select_one(root_sel)
        if root is not None:
            scope = root

    def pick(key: str) -> str:
        sel = detail.get(key)
        if not sel:
            return ""
        el = scope.select_one(sel)
        if el is None:
            return ""
        # If meta tag, prefer content attribute
        if getattr(el, "name", "").lower() == "meta":
            val = el.get("content")
            return str(val) if val is not None else ""
        return el.get_text(strip=True)

    brand = pick("brand").strip()
    name = pick("name").strip()
    mpn = pick("mpn").strip()
    # Price: support meta content or HTML amounts
    price_s = ""
    price_sel = detail.get("price") or ""
    price_el = scope.select_one(price_sel) if price_sel else None
    if price_el is not None:
        # If <meta>, use its content; otherwise parse the container via _price_text
        if getattr(price_el, "name", "").lower() == "meta":
            price_s = str(price_el.get("content") or "")
        else:
            price_s = _price_text(price_el)
    in_stock_s = pick("in_stock")
    lead_s = pick("lead_time_days")

    if not brand and name:
        brand = name.split()[0]

    # Fallback: if MPN missing, try to extract from meta text (e.g., "COD: XYZ")
    if not mpn:
        meta_el = scope.select_one(".product_meta")
        meta_text = meta_el.get_text(" ", strip=True) if meta_el else ""
        import re

        m = re.search(r"\bCOD[:\s]+([\w\-\./]+)", meta_text, flags=re.IGNORECASE)
        if m:
            mpn = m.group(1).strip()
    # Fallback 2: if still missing, parse product id from og:url (/product/<id>/...)
    if not mpn:
        url_meta = scope.select_one("meta[property='og:url']")
        if url_meta and url_meta.get("content"):
            import re

            mm = re.search(r"/product/(\d+)/", str(url_meta.get("content")))
            if mm:
                mpn = mm.group(1)

    mpn = mpn.strip()
    category = pick("category").strip()
    # Prefer breadcrumb category when available
    trail = soup.select("ol.breadcrumb li a, #breadcrumb .breadcrumb li a")
    for a in reversed(trail):
        href = str(a.get("href") or "")
        if "/category/" in href:
            ct = a.get_text(strip=True)
            if ct:
                category = ct
                break

    if not brand or not mpn or not price_s:
        return None, None

    in_stock = _to_bool(in_stock_s) if in_stock_s else True
    lead = int(lead_s) if (lead_s and lead_s.isdigit()) else None

    p = ProductInput(
        brand=brand,
        mpn=mpn,
        ean=None,
        name=name or f"{brand} {mpn}",
        category=(category or None),
        speed=None,
        brake=None,
        axle=None,
        rotor=None,
        freehub=None,
    )
    # Optional dealer-specific code in detail mapping
    dealer_code = pick("dealer_code").strip()
    o = OfferInput(
        brand=brand,
        mpn=mpn,
        supplier=mapping["supplier"],
        price=_to_price(price_s),
        in_stock=in_stock,
        lead_time_days=lead,
        extra={"dealer_pn": dealer_code} if dealer_code else {},
    )
    return p, o


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
            timeout=10.0,
            headers=headers or {"User-Agent": "BikeCopilotBot/0.1"},
            follow_redirects=True,
        ) as client:
            r = client.get(u)
            r.raise_for_status()
            return r.text

    # Helpers to reduce complexity
    def _parse_listing_or_detail(base_url: str, html_text: str) -> None:
        """Parse a listing page, optionally following detail links if mapping provides them."""
        item_link_sel = mapping.get("item_link")
        has_detail = bool(mapping.get("detail"))
        if item_link_sel and has_detail:
            soup = BeautifulSoup(html_text, "html.parser")
            rows = soup.select(mapping["root"])  # type: ignore[index]
            for r in rows:
                a = r.select_one(item_link_sel)
                href_attr = a.get("href") if a else None
                href = _abs_url(base_url, str(href_attr) if href_attr is not None else None)
                if not href or href in seen_pages:
                    continue
                seen_pages.add(href)
                time.sleep(max(0.0, delay_sec))
                try:
                    dhtml = _fetch(href)
                except Exception:
                    continue
                p1, o1 = parse_detail_html(dhtml, mapping)
                if p1 and o1:
                    if not any((pp.brand, pp.mpn) == (p1.brand, p1.mpn) for pp in all_products):
                        all_products.append(p1)
                    if not any((oo.brand, oo.mpn, oo.supplier) == (o1.brand, o1.mpn, o1.supplier) for oo in all_offers):
                        all_offers.append(o1)
        else:
            p, o = parse_html(html_text, mapping)
            all_products.extend(p)
            all_offers.extend(o)

    def _pagination_chain(first_html: str, first_url: str) -> list[tuple[str, str]]:
        """Return list of (url, html) for next pages up to max_pages-1 (excluding the first).

        Joins relative links to absolute using the last fetched page as base.
        """
        out: list[tuple[str, str]] = []
        if not (follow_next and isinstance(mapping.get("pagination"), dict)):
            return out
        next_sel = mapping.get("pagination", {}).get("next")  # type: ignore[union-attr]
        if not next_sel:
            return out
        page_count = 1
        current_html = first_html
        current_url = first_url
        while page_count < max_pages:
            soup = BeautifulSoup(current_html, "html.parser")
            nxt = soup.select_one(next_sel)
            if nxt is None:
                break
            href_attr = nxt.get("href") if nxt else None
            href = _abs_url(current_url, str(href_attr) if href_attr is not None else None)
            if not href or href in seen_pages:
                break
            seen_pages.add(href)
            time.sleep(max(0.0, delay_sec))
            try:
                next_html = _fetch(href)
            except Exception:
                break
            out.append((href, next_html))
            current_html = next_html
            current_url = href
            page_count += 1
        return out

    for seed in urls:
        if seed in seen_pages:
            continue
        seen_pages.add(seed)
        try:
            html = _fetch(seed)
        except Exception:
            continue
        _parse_listing_or_detail(seed, html)
        for href, html2 in _pagination_chain(html, seed):
            _parse_listing_or_detail(href, html2)

    return all_products, all_offers


def build_search_urls(query: str, mapping_yaml: Path) -> list[str]:
    mapping = _load_mapping(mapping_yaml)
    s = mapping.get("search")
    if not s or ("url_template" not in s):
        raise ValueError("mapping.search.url_template is required for search-web")
    tmpl = s.get("url_template", "")
    from urllib.parse import quote_plus

    return [tmpl.format(q=quote_plus(query))]


def parse_sitemap_urls(
    sitemap_url: str, headers: dict[str, str] | None = None, limit: int | None = None
) -> list[str]:
    """Parse a sitemap index or urlset and return a list of <loc> URLs.

    If it's an index, fetch child sitemaps. Applies an optional limit.
    """
    import httpx
    import xml.etree.ElementTree as ET

    seen: set[str] = set()

    def _fetch(u: str) -> str:
        with httpx.Client(
            timeout=10.0,
            headers=headers or {"User-Agent": "BikeCopilotBot/0.1"},
            follow_redirects=True,
        ) as client:
            r = client.get(u)
            r.raise_for_status()
            return r.text

    def _parse(xml_text: str) -> list[str]:
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        urls: list[str] = []
        if root.tag.endswith("sitemapindex"):
            for sm in root.findall(f"{ns}sitemap"):
                loc = sm.findtext(f"{ns}loc") or ""
                if loc and loc not in seen:
                    seen.add(loc)
                    child = _fetch(loc)
                    urls.extend(_parse(child))
        elif root.tag.endswith("urlset"):
            for u in root.findall(f"{ns}url"):
                loc = u.findtext(f"{ns}loc") or ""
                if loc:
                    urls.append(loc)
        return urls

    xml = _fetch(sitemap_url)
    urls = _parse(xml)
    if limit is not None and limit > 0:
        return urls[:limit]
    return urls
