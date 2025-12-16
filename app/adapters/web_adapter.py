from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, NotRequired, TypedDict, TYPE_CHECKING
from urllib.parse import parse_qsl, urlencode, urlparse

from bs4 import BeautifulSoup
import yaml

from ..types import OfferInput, ProductInput

if TYPE_CHECKING:
    import httpx

ProgressCallback = Callable[[str, int, int, int], None]


class PaginationMapping(TypedDict, total=False):
    next: str  # CSS selector for the "next page" link
    mode: str  # "link" (default) or "query"
    param: str  # query parameter name for skip-based pagination
    limit: int  # fallback items per page for query pagination
    limit_selector: str  # CSS selector whose text is the per-page limit


class SearchMapping(TypedDict, total=False):
    url_template: str  # e.g. https://shop.example/search?q={q}


class WebMapping(TypedDict, total=False):
    supplier: str
    root: str
    brand: str
    mpn: str
    name: str
    price: str
    category: str
    in_stock: NotRequired[str]
    lead_time_days: NotRequired[str]
    dealer_code: NotRequired[str]
    pagination: NotRequired[PaginationMapping]
    search: NotRequired[SearchMapping]
    item_link: NotRequired[str]
    detail: NotRequired[
        dict[str, str]
    ]  # may include keys: name, price, brand, mpn, in_stock, lead_time_days, category, dealer_code


@dataclass
class FetchContext:
    mapping: WebMapping
    follow_next: bool
    max_pages: int
    delay_sec: float
    progress_cb: ProgressCallback | None
    fetch_fn: Callable[[str], str]
    seen_pages: set[str]
    all_products: list[ProductInput]
    all_offers: list[OfferInput]


def _load_mapping(path: Path) -> WebMapping:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    required = {"supplier", "root", "brand", "mpn", "name", "price"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"mapping YAML missing keys: {sorted(missing)}")
    mapping: WebMapping = {
        "supplier": str(data.get("supplier", "")),
        "root": str(data.get("root", "")),
        "brand": str(data.get("brand", "")),
        "mpn": str(data.get("mpn", "")),
        "name": str(data.get("name", "")),
        "price": str(data.get("price", "")),
    }
    # Optional fields
    if "category" in data:
        mapping["category"] = str(data.get("category") or "")
    if "dealer_code" in data:
        mapping["dealer_code"] = str(data.get("dealer_code") or "")
    if "in_stock" in data:
        mapping["in_stock"] = str(data.get("in_stock") or "")
    if "lead_time_days" in data:
        mapping["lead_time_days"] = str(data.get("lead_time_days") or "")
    if "pagination" in data and isinstance(data.get("pagination"), dict):
        mapping["pagination"] = data["pagination"]  # type: ignore[assignment]
    if "search" in data and isinstance(data.get("search"), dict):
        mapping["search"] = data["search"]  # type: ignore[assignment]
    if "item_link" in data:
        mapping["item_link"] = str(data.get("item_link") or "")
    if "detail" in data and isinstance(data.get("detail"), dict):
        mapping["detail"] = data["detail"]  # type: ignore[assignment]
    return mapping


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
    t = (
        s.strip()
        .replace("€", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace("\u202f", "")
    )
    # Handle thousands separator "." with decimal "," (e.g. 1.349,00)
    if "," in t and "." in t and t.find(",") > t.find("."):
        t = t.replace(".", "")
    # handle 12,34 and 12.34
    if "," in t and t.count(",") == 1:
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
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


def _safe_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _page_has_results(html: str, selector: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.select(selector))


def _build_query_url(base_url: str, query: dict[str, str]) -> str:
    parts = urlparse(base_url)
    encoded = urlencode(query, doseq=True)
    return parts._replace(query=encoded).geturl()


def parse_html(
    html: str, mapping: WebMapping
) -> tuple[list[ProductInput], list[OfferInput]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(mapping["root"])  # type: ignore[index]
    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    for r in rows:
        product, offer = _parse_listing_row(r, mapping)
        if product is None or offer is None:
            continue
        products.append(product)
        offers.append(offer)
    return products, offers


def _parse_listing_row(
    row, mapping: WebMapping
) -> tuple[ProductInput | None, OfferInput | None]:
    brand, mpn, name, price_s = _listing_core_fields(row, mapping)
    if not brand or not mpn or not price_s:
        return None, None
    if not any(ch.isdigit() for ch in price_s):
        return None, None
    category = _listing_category(row, mapping)
    in_stock = _listing_in_stock(row, mapping)
    lead = _listing_lead_time(row, mapping)
    product = _build_listing_product(brand, mpn, name, category)
    offer = _build_listing_offer(row, mapping, brand, mpn, price_s, in_stock, lead)
    return product, offer


def _listing_basic_fields(row, mapping: WebMapping) -> tuple[str, str, str]:
    brand = _text(row.select_one(mapping["brand"]))
    mpn = _text(row.select_one(mapping["mpn"]))
    name = _text(row.select_one(mapping["name"]))
    return brand, mpn, name


def _listing_core_fields(row, mapping: WebMapping) -> tuple[str, str, str, str]:
    brand, mpn, name = _listing_basic_fields(row, mapping)
    price_s = _price_text(row.select_one(mapping["price"]))
    return brand, mpn, name, price_s


def _listing_category(row, mapping: WebMapping) -> str | None:
    category = None
    if "category" in mapping:
        category = _text(row.select_one(mapping["category"])) or None
    return category


def _listing_in_stock(row, mapping: WebMapping) -> bool:
    if "in_stock" not in mapping:
        return True
    return _to_bool(_text(row.select_one(mapping["in_stock"])) or "")


def _listing_lead_time(row, mapping: WebMapping) -> int | None:
    if "lead_time_days" not in mapping:
        return None
    lead_t = _text(row.select_one(mapping["lead_time_days"]))
    return int(lead_t) if lead_t.isdigit() else None


def _build_listing_product(
    brand: str,
    mpn: str,
    name: str,
    category: str | None,
) -> ProductInput:
    return ProductInput(
        brand=brand,
        mpn=mpn,
        ean=None,
        name=name or f"{brand} {mpn}",
        category=category or None,
        speed=None,
        brake=None,
        axle=None,
        rotor=None,
        freehub=None,
    )


def _build_listing_offer(
    row,
    mapping: WebMapping,
    brand: str,
    mpn: str,
    price_s: str,
    in_stock: bool,
    lead: int | None,
) -> OfferInput:
    dealer_code = None
    if "dealer_code" in mapping:
        dealer_code = _text(row.select_one(mapping["dealer_code"])) or None
    return OfferInput(
        brand=brand,
        mpn=mpn,
        supplier=mapping["supplier"],
        price=_to_price(price_s),
        in_stock=in_stock,
        lead_time_days=lead,
        extra={"dealer_pn": dealer_code} if dealer_code else {},
    )


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
    scope = _detail_scope(soup, detail)
    brand, name, mpn, price_s, in_stock_s, lead_s, category, dealer_code = (
        _extract_detail_fields(scope, soup, detail)
    )

    if not brand or not mpn or not price_s:
        return None, None

    in_stock = _to_bool(in_stock_s) if in_stock_s else True
    lead = int(lead_s) if (lead_s and lead_s.isdigit()) else None
    p = _build_detail_product(brand, mpn, name, category)
    o = _build_detail_offer(
        brand, mpn, price_s, in_stock, lead, dealer_code, mapping["supplier"]
    )
    return p, o


def _detail_scope(soup, detail: dict[str, str]):
    scope = soup
    root_sel = detail.get("root")
    if root_sel:
        root = soup.select_one(root_sel)
        if root is not None:
            scope = root
    return scope


def _build_detail_product(
    brand: str,
    mpn: str,
    name: str,
    category: str,
) -> ProductInput:
    return ProductInput(
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


def _build_detail_offer(
    brand: str,
    mpn: str,
    price_s: str,
    in_stock: bool,
    lead: int | None,
    dealer_code: str,
    supplier: str,
) -> OfferInput:
    return OfferInput(
        brand=brand,
        mpn=mpn,
        supplier=supplier,
        price=_to_price(price_s),
        in_stock=in_stock,
        lead_time_days=lead,
        extra={"dealer_pn": dealer_code} if dealer_code else {},
    )


def _extract_detail_fields(
    scope,
    soup,
    detail: dict[str, str],
) -> tuple[str, str, str, str, str, str, str, str]:
    def pick(key: str) -> str:
        sel = detail.get(key)
        if not sel:
            return ""
        el = scope.select_one(sel)
        if el is None:
            return ""
        if getattr(el, "name", "").lower() == "meta":
            val = el.get("content")
            return str(val) if val is not None else ""
        return el.get_text(strip=True)

    brand, name, mpn = _detail_identity(scope, detail, pick)
    price_s = _detail_price(scope, detail)
    in_stock_s = pick("in_stock")
    lead_s = pick("lead_time_days")

    mpn = _fallback_mpn(scope, mpn)
    category = _detail_category(scope, soup, detail)
    dealer_code = pick("dealer_code").strip()
    return brand, name, mpn, price_s, in_stock_s, lead_s, category, dealer_code


def _detail_identity(
    scope,
    detail: dict[str, str],
    pick: Callable[[str], str],
) -> tuple[str, str, str]:
    brand = pick("brand").strip()
    name = pick("name").strip()
    mpn = pick("mpn").strip()
    if not brand and name:
        brand = name.split()[0]
    return brand, name, mpn


def _detail_price(scope, detail: dict[str, str]) -> str:
    price_sel = detail.get("price") or ""
    price_el = scope.select_one(price_sel) if price_sel else None
    if price_el is None:
        return ""
    if getattr(price_el, "name", "").lower() == "meta":
        return str(price_el.get("content") or "")
    return _price_text(price_el)


def _fallback_mpn(scope, mpn: str) -> str:
    if mpn:
        return mpn.strip()
    meta_el = scope.select_one(".product_meta")
    meta_text = meta_el.get_text(" ", strip=True) if meta_el else ""
    import re

    m = re.search(r"\bCOD[:\s]+([\w\-\./]+)", meta_text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    url_meta = scope.select_one("meta[property='og:url']")
    if url_meta and url_meta.get("content"):
        mm = re.search(r"/product/(\d+)/", str(url_meta.get("content")))
        if mm:
            return mm.group(1)
    return mpn.strip()


def _detail_category(scope, soup, detail: dict[str, str]) -> str:
    category = ""
    sel = detail.get("category")
    if sel:
        el = scope.select_one(sel)
        if el is not None:
            category = el.get_text(strip=True)
    trail = soup.select("ol.breadcrumb li a, #breadcrumb .breadcrumb li a")
    for a in reversed(trail):
        href = str(a.get("href") or "")
        if "/category/" in href:
            ct = a.get_text(strip=True)
            if ct:
                category = ct
                break
    return category


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
    session: "httpx.Client | None" = None,
    progress_cb: ProgressCallback | None = None,
) -> tuple[list[ProductInput], list[OfferInput]]:
    """Fetch one or more URLs and parse them using the provided mapping.

    - If follow_next is True and mapping.pagination.next is set, follows next links up to max_pages.
    - headers can include cookies/auth; keep polite delays via delay_sec.
    """
    import time

    mapping = _load_mapping(mapping_yaml)
    fetch_fn = _build_fetch_fn(headers=headers, session=session)
    return _fetch_and_parse_urls_impl(
        urls,
        mapping,
        follow_next,
        max_pages,
        delay_sec,
        progress_cb,
        fetch_fn,
        time,
    )


def _build_fetch_fn(
    *,
    headers: dict[str, str] | None,
    session: "httpx.Client | None",
) -> Callable[[str], str]:
    import httpx

    def _fetch(u: str) -> str:
        if session is not None:
            r = session.get(u)
            r.raise_for_status()
            return r.text
        with httpx.Client(
            timeout=10.0,
            headers=headers or {"User-Agent": "BikeCopilotBot/0.1"},
            follow_redirects=True,
        ) as client:
            r = client.get(u)
            r.raise_for_status()
            return r.text

    return _fetch


def _fetch_and_parse_urls_impl(
    urls: list[str],
    mapping: WebMapping,
    follow_next: bool,
    max_pages: int,
    delay_sec: float,
    progress_cb: ProgressCallback | None,
    fetch_fn: Callable[[str], str],
    time_mod,
) -> tuple[list[ProductInput], list[OfferInput]]:
    ctx = FetchContext(
        mapping=mapping,
        follow_next=follow_next,
        max_pages=max_pages,
        delay_sec=delay_sec,
        progress_cb=progress_cb,
        fetch_fn=fetch_fn,
        seen_pages=set(),
        all_products=[],
        all_offers=[],
    )
    for seed in urls:
        _process_seed_url(
            seed,
            ctx,
            time_mod,
        )

    return ctx.all_products, ctx.all_offers


def _process_seed_url(
    seed: str,
    ctx: FetchContext,
    time_mod,
) -> None:
    if _seed_already_seen(seed, ctx.seen_pages):
        return
    html = _safe_fetch(ctx.fetch_fn, seed)
    _process_seed_html(
        html,
        seed,
        ctx,
        time_mod,
    )


def _process_seed_html(
    html: str | None,
    seed: str,
    ctx: FetchContext,
    time_mod,
) -> None:
    if html is None:
        return
    _process_seed_first_page(
        html,
        seed,
        ctx,
        time_mod,
    )
    _process_seed_pagination(
        html,
        seed,
        ctx,
        time_mod,
    )


def _process_seed_first_page(
    html: str,
    seed: str,
    ctx: FetchContext,
    time_mod,
) -> None:
    _process_page_html(
        seed,
        html,
        ctx.mapping,
        ctx.delay_sec,
        ctx.seen_pages,
        ctx.all_products,
        ctx.all_offers,
        ctx.fetch_fn,
        time_mod,
    )
    _report_progress(ctx.progress_cb, seed, 1, ctx.all_products, ctx.all_offers)


def _process_seed_pagination(
    html: str,
    seed: str,
    ctx: FetchContext,
    time_mod,
) -> None:
    pages = _collect_paginated_pages(
        html,
        seed,
        ctx,
    )
    _process_additional_pages(
        pages,
        ctx.mapping,
        ctx.delay_sec,
        ctx.seen_pages,
        ctx.all_products,
        ctx.all_offers,
        ctx.fetch_fn,
        time_mod,
        ctx.progress_cb,
    )


def _seed_already_seen(seed: str, seen_pages: set[str]) -> bool:
    if seed in seen_pages:
        return True
    seen_pages.add(seed)
    return False


def _process_page_html(
    url: str,
    html: str,
    mapping: WebMapping,
    delay_sec: float,
    seen_pages: set[str],
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
    fetch_fn: Callable[[str], str],
    time_mod,
) -> None:
    _parse_listing_or_detail(
        url,
        html,
        mapping,
        delay_sec,
        seen_pages,
        all_products,
        all_offers,
        fetch_fn,
        time_mod,
    )


def _process_additional_pages(
    pages: list[tuple[str, str]],
    mapping: WebMapping,
    delay_sec: float,
    seen_pages: set[str],
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
    fetch_fn: Callable[[str], str],
    time_mod,
    progress_cb: ProgressCallback | None,
) -> None:
    for page_idx, (href, html) in enumerate(pages, start=2):
        _process_page_html(
            href,
            html,
            mapping,
            delay_sec,
            seen_pages,
            all_products,
            all_offers,
            fetch_fn,
            time_mod,
        )
        _report_progress(progress_cb, href, page_idx, all_products, all_offers)


def _report_progress(
    progress_cb: ProgressCallback | None,
    url: str,
    page_idx: int,
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
) -> None:
    if not progress_cb:
        return
    progress_cb(url, page_idx, len(all_products), len(all_offers))


def _parse_listing_or_detail(
    base_url: str,
    html_text: str,
    mapping: WebMapping,
    delay_sec: float,
    seen_pages: set[str],
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
    fetch_fn: Callable[[str], str],
    time_mod,
) -> None:
    item_link_sel = mapping.get("item_link")
    has_detail = bool(mapping.get("detail"))
    if item_link_sel and has_detail:
        _parse_with_detail_links(
            base_url,
            html_text,
            item_link_sel,
            mapping,
            delay_sec,
            seen_pages,
            all_products,
            all_offers,
            fetch_fn,
            time_mod,
        )
    else:
        products, offers = parse_html(html_text, mapping)
        all_products.extend(products)
        all_offers.extend(offers)


def _parse_with_detail_links(
    base_url: str,
    html_text: str,
    item_link_sel: str,
    mapping: WebMapping,
    delay_sec: float,
    seen_pages: set[str],
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
    fetch_fn: Callable[[str], str],
    time_mod,
) -> None:
    soup = BeautifulSoup(html_text, "html.parser")
    rows = soup.select(mapping["root"])  # type: ignore[index]
    for row in rows:
        _follow_detail_link_for_row(
            row,
            base_url,
            item_link_sel,
            mapping,
            delay_sec,
            seen_pages,
            all_products,
            all_offers,
            fetch_fn,
            time_mod,
        )


def _follow_detail_link_for_row(
    row,
    base_url: str,
    item_link_sel: str,
    mapping: WebMapping,
    delay_sec: float,
    seen_pages: set[str],
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
    fetch_fn: Callable[[str], str],
    time_mod,
) -> None:
    anchor = row.select_one(item_link_sel)
    href_attr = anchor.get("href") if anchor else None
    href = _abs_url(base_url, str(href_attr) if href_attr is not None else None)
    if not href or href in seen_pages:
        return
    seen_pages.add(href)
    _sleep_with_delay(time_mod, delay_sec)
    detail_html = _safe_fetch(fetch_fn, href)
    if detail_html is None:
        return
    product, offer = parse_detail_html(detail_html, mapping)
    if product and offer:
        _append_unique_product_offer(product, offer, all_products, all_offers)


def _sleep_with_delay(time_mod, delay_sec: float) -> None:
    time_mod.sleep(max(0.0, delay_sec))


def _safe_fetch(fetch_fn: Callable[[str], str], url: str) -> str | None:
    try:
        return fetch_fn(url)
    except Exception:
        return None


def _append_unique_product_offer(
    product: ProductInput,
    offer: OfferInput,
    all_products: list[ProductInput],
    all_offers: list[OfferInput],
) -> None:
    if not any(
        (pp.brand, pp.mpn) == (product.brand, product.mpn) for pp in all_products
    ):
        all_products.append(product)
    if not any(
        (oo.brand, oo.mpn, oo.supplier) == (offer.brand, offer.mpn, offer.supplier)
        for oo in all_offers
    ):
        all_offers.append(offer)


def _collect_paginated_pages(
    first_html: str,
    first_url: str,
    ctx: FetchContext,
) -> list[tuple[str, str]]:
    pagination_cfg = _pagination_config(ctx.mapping)
    if not _should_paginate(ctx.follow_next, pagination_cfg):
        return []
    mode = _pagination_mode(pagination_cfg)
    if mode == "query":
        return _pagination_chain_query(
            pagination_cfg,
            first_html,
            first_url,
            ctx,
        )
    return _pagination_chain_link(
        pagination_cfg,
        first_html,
        first_url,
        ctx.max_pages,
        ctx.seen_pages,
        ctx.delay_sec,
        ctx.fetch_fn,
    )


def _should_paginate(
    follow_next: bool, pagination_cfg: PaginationMapping | None
) -> bool:
    return bool(follow_next and pagination_cfg)


def _pagination_mode(pcfg: PaginationMapping | None) -> str:
    if pcfg is None:
        return "none"
    mode_value = pcfg.get("mode")
    return mode_value.lower() if isinstance(mode_value, str) else "link"


def _pagination_chain_link(
    pcfg: PaginationMapping | None,
    first_html: str,
    first_url: str,
    max_pages: int,
    seen_pages: set[str],
    delay_sec: float,
    fetch_fn: Callable[[str], str],
) -> list[tuple[str, str]]:
    import time as _time

    if pcfg is None:
        return []

    next_sel_raw = pcfg.get("next")
    next_sel = next_sel_raw if isinstance(next_sel_raw, str) else ""
    if not next_sel:
        return []
    return _pagination_link_loop(
        next_sel,
        first_html,
        first_url,
        max_pages,
        seen_pages,
        delay_sec,
        fetch_fn,
        _time,
    )


def _pagination_link_loop(
    next_sel: str,
    first_html: str,
    first_url: str,
    max_pages: int,
    seen_pages: set[str],
    delay_sec: float,
    fetch_fn: Callable[[str], str],
    time_mod,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    current_html = first_html
    current_url = first_url
    for _ in range(max_pages - 1):
        soup = BeautifulSoup(current_html, "html.parser")
        href = _next_page_href(soup, next_sel, current_url, seen_pages)
        if not href:
            break
        time_mod.sleep(max(0.0, delay_sec))
        next_html = _safe_fetch(fetch_fn, href)
        if next_html is None:
            break
        out.append((href, next_html))
        current_html = next_html
        current_url = href
    return out


def _pagination_config(mapping: WebMapping) -> PaginationMapping | None:
    raw = mapping.get("pagination")
    return raw if isinstance(raw, dict) else None


def _resolve_query_limit(
    pcfg: PaginationMapping,
    first_html: str,
) -> int | None:
    selector = pcfg.get("limit_selector")
    if isinstance(selector, str) and selector:
        soup = BeautifulSoup(first_html, "html.parser")
        node = soup.select_one(selector)
        if node:
            limit_candidate = _safe_int(node.get_text(strip=True), 0)
            if limit_candidate > 0:
                return limit_candidate
    limit_cfg = pcfg.get("limit")
    if isinstance(limit_cfg, int) and limit_cfg > 0:
        return limit_cfg
    return None


def _pagination_chain_query(
    pcfg: PaginationMapping | None,
    first_html: str,
    first_url: str,
    ctx: FetchContext,
) -> list[tuple[str, str]]:
    import time as _time

    if pcfg is None:
        return []
    limit = _resolve_query_limit(pcfg, first_html)
    if limit is None or limit <= 0:
        return []
    param_raw = pcfg.get("param")
    param_name = param_raw if isinstance(param_raw, str) and param_raw else "skip"
    base_query, start_skip = _initial_pagination_state(first_url, param_name)
    return _pagination_query_loop(
        first_url,
        base_query,
        param_name,
        start_skip,
        limit,
        ctx,
        _time,
    )


def _pagination_query_loop(
    first_url: str,
    base_query: dict[str, str],
    param_name: str,
    start_skip: int,
    limit: int,
    ctx: FetchContext,
    time_mod,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    current_skip = start_skip
    root_selector = ctx.mapping["root"]
    for _ in range(ctx.max_pages - 1):
        next_skip, next_url = _next_paginated_url(
            first_url, base_query, param_name, current_skip, limit
        )
        if next_url in ctx.seen_pages:
            break
        ctx.seen_pages.add(next_url)
        time_mod.sleep(max(0.0, ctx.delay_sec))
        next_html = _safe_fetch(ctx.fetch_fn, next_url)
        if next_html is None:
            break
        if not _page_has_results(next_html, root_selector):
            break
        out.append((next_url, next_html))
        current_skip = next_skip
    return out


def _next_page_href(
    soup,
    next_sel: str,
    current_url: str,
    seen_pages: set[str],
) -> str | None:
    nxt = soup.select_one(next_sel)
    if nxt is None:
        return None
    href_attr = nxt.get("href")
    href = _abs_url(current_url, str(href_attr) if href_attr is not None else None)
    if not href or href in seen_pages:
        return None
    seen_pages.add(href)
    return href


def _initial_pagination_state(
    first_url: str,
    param_name: str,
) -> tuple[dict[str, str], int]:
    base_parts = urlparse(first_url)
    base_query = dict(parse_qsl(base_parts.query, keep_blank_values=True))
    start_skip = _safe_int(base_query.get(param_name), 0)
    return base_query, start_skip


def _next_paginated_url(
    first_url: str,
    base_query: dict[str, str],
    param_name: str,
    current_skip: int,
    limit: int,
) -> tuple[int, str]:
    next_skip = current_skip + limit
    query = dict(base_query)
    query[param_name] = str(next_skip)
    next_url = _build_query_url(first_url, query)
    return next_skip, next_url


def build_search_urls(query: str, mapping_yaml: Path) -> list[str]:
    mapping = _load_mapping(mapping_yaml)
    s = mapping.get("search")
    if not s or ("url_template" not in s):
        raise ValueError("mapping.search.url_template is required for search-web")
    tmpl = s.get("url_template", "")
    from urllib.parse import quote_plus

    return [tmpl.format(q=quote_plus(query))]


def parse_sitemap_urls(
    sitemap_url: str,
    headers: dict[str, str] | None = None,
    limit: int | None = None,
    session: "httpx.Client | None" = None,
) -> list[str]:
    """Parse sitemap XML from a URL and return the list of <loc> URLs."""
    import httpx

    def _fetch(u: str) -> str:
        if session is not None:
            r = session.get(u)
            r.raise_for_status()
            return r.text
        with httpx.Client(
            timeout=10.0,
            headers=headers or {"User-Agent": "BikeCopilotBot/0.1"},
            follow_redirects=True,
        ) as client:
            r = client.get(u)
            r.raise_for_status()
            return r.text

    xml = _fetch(sitemap_url)
    urls = _parse_sitemap_xml(xml, _fetch)
    if limit is not None and limit > 0:
        return urls[:limit]
    return urls


def _parse_sitemap_xml(
    xml_text: str,
    fetch_fn: Callable[[str], str],
) -> list[str]:
    import xml.etree.ElementTree as ET

    seen: set[str] = set()
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    urls: list[str] = []
    if root.tag.endswith("sitemapindex"):
        for sm in root.findall(f"{ns}sitemap"):
            loc = sm.findtext(f"{ns}loc") or ""
            if not loc or loc in seen:
                continue
            seen.add(loc)
            child = fetch_fn(loc)
            urls.extend(_parse_sitemap_xml(child, fetch_fn))
    elif root.tag.endswith("urlset"):
        for u in root.findall(f"{ns}url"):
            loc = u.findtext(f"{ns}loc") or ""
            if loc:
                urls.append(loc)
    return urls
