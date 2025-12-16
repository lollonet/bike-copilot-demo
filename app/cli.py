from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict
from urllib.parse import parse_qs, urlparse

import rich
from pydantic import BaseModel
import typer
from rich.table import Table
import os
import random
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, func, asc

from .adapters.csv_adapter import parse_offers_csv, parse_products_csv
from .adapters.pdf_adapter import extract_from_pdf
from .adapters.web_adapter import (
    parse_file as parse_web_file,
    fetch_and_parse_urls,
    build_search_urls,
    parse_sitemap_urls,
)
from .adapters.csv_mapped_adapter import parse_unified_csv
from .ingest import IngestStats, upsert
from .models import (
    EventLog,
    SessionLocal,
    SupplierOffer,
    Product,
    create_all,
    PNMapping,
)
from .quote import render_quote
from .search import search
from .types import Brake, Freehub, OfferInput, QuoteResponse, Rotor, SearchRequest
from .policy import parse_policy_html
from .models import DealerPolicy
from .dealers import DealerConfig, DealerLoginConfig, find_dealer


app = typer.Typer(add_completion=True, no_args_is_help=True, help="Bike Copilot CLI")


def _offer_id_completions(incomplete: str) -> list[str]:
    create_all()
    with SessionLocal() as db:
        rows_seq = db.execute(
            select(
                SupplierOffer.id,
                Product.brand,
                Product.mpn,
                SupplierOffer.supplier,
                SupplierOffer.price,
            ).join(Product, SupplierOffer.product_id == Product.id)
        ).all()
        rows = [
            (
                int(r[0]),
                str(r[1]),
                str(r[2]),
                str(r[3]),
                float(r[4]) if r[4] is not None else None,
            )
            for r in rows_seq
        ]
    # complete by id prefix
    inc = incomplete.strip()
    values = (
        [str(r[0]) for r in rows if str(r[0]).startswith(inc)]
        if inc
        else [str(r[0]) for r in rows]
    )
    return values[:50]


@app.callback()
def _init() -> None:
    """Ensure DB is ready."""
    create_all()


class ExportRow(BaseModel):
    brand: str
    mpn: str
    name: str
    category: str | None = None
    supplier: str
    price: float
    in_stock: bool
    lead_time_days: int | None = None


def _escape_md(text: str) -> str:
    return text.replace("|", "\\|")


class AliasEntry(TypedDict, total=False):
    maker_pn: str
    dealer_pn: str
    confidence: float


class AliasBlock(TypedDict, total=False):
    dealer: str | None
    aliases: list[AliasEntry]


def _build_headers_from_cli(header: list[str] | None) -> dict[str, str]:
    hdrs: dict[str, str] = {}
    for h in header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            hdrs[k.strip()] = v.strip()
    return hdrs


@app.command("dump-md")
def dump_md(
    limit: int | None = typer.Option(None, help="Max rows; omit for all"),
    supplier: str | None = typer.Option(None, help="Filter by supplier"),
    brand: str | None = typer.Option(None, help="Filter by brand"),
    category: str | None = typer.Option(None, help="Filter by category"),
) -> None:
    """Dump joined product+offer rows as a Markdown table for inspection."""
    rows = _query_export_rows(limit, supplier, brand, category)
    items = _build_export_rows(rows)
    table = _render_export_table(items)
    print(table)


def _query_export_rows(
    limit: int | None,
    supplier: str | None,
    brand: str | None,
    category: str | None,
) -> list[
    tuple[SupplierOffer, str, float, bool, int | None, str, str, str, str | None]
]:
    with SessionLocal() as db:
        stmt = (
            select(
                SupplierOffer,
                SupplierOffer.supplier,
                SupplierOffer.price,
                SupplierOffer.in_stock,
                SupplierOffer.lead_time_days,
                Product.brand,
                Product.mpn,
                Product.name,
                Product.category,
            )
            .join(Product, SupplierOffer.product_id == Product.id)
            .order_by(asc(Product.brand), asc(Product.mpn), asc(SupplierOffer.supplier))
        )
        if supplier:
            stmt = stmt.where(SupplierOffer.supplier == supplier)
        if brand:
            stmt = stmt.where(Product.brand == brand)
        if category:
            stmt = stmt.where(Product.category == category)
        if isinstance(limit, int) and limit > 0:
            stmt = stmt.limit(limit)
        rows_raw = db.execute(stmt).all()
        rows = [tuple(r) for r in rows_raw]
    return rows


def _build_export_rows(
    rows: list[
        tuple[SupplierOffer, str, float, bool, int | None, str, str, str, str | None]
    ],
) -> list[ExportRow]:
    items: list[ExportRow] = []
    for _offer, sup, price, in_stock, lead, br, mpn, name, cat in rows:
        items.append(
            ExportRow(
                brand=str(br or ""),
                mpn=str(mpn or ""),
                name=str(name or ""),
                category=str(cat) if cat is not None else None,
                supplier=str(sup or ""),
                price=float(price or 0.0),
                in_stock=bool(in_stock),
                lead_time_days=int(lead) if lead is not None else None,
            )
        )
    return items


def _render_export_table(items: list[ExportRow]) -> str:
    header = "| brand | mpn | name | category | supplier | price | in_stock | lead_time_days |"
    sep = "|---|---|---|---|---|---:|---:|---:|"
    lines: list[str] = [header, sep]
    for it in items:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_md(it.brand),
                    _escape_md(it.mpn),
                    _escape_md(it.name),
                    _escape_md(it.category or ""),
                    _escape_md(it.supplier),
                    f"{it.price:.2f}",
                    ("yes" if it.in_stock else "no"),
                    (str(it.lead_time_days) if it.lead_time_days is not None else ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


@app.command("pn-alias-import")
def pn_alias_import(
    yaml_file: Path = typer.Argument(
        ..., exists=True, dir_okay=False, help="YAML con alias PN per dealer"
    ),
) -> None:
    """Import PN alias pairs from a YAML file.

    YAML structure:
    - dealer: DealerA
      aliases:
        - maker_pn: CN-HG601
          dealer_pn: ICNHG601116
          confidence: 0.98
    """
    import yaml

    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise typer.BadParameter("YAML root must be a list of dealer blocks")
    create_all()
    with SessionLocal() as db:
        norm_to_product = _build_norm_mpn_index(db)
        inserted, updated = _apply_pn_alias_blocks(db, data, norm_to_product)
    rich.print(
        f"[green]Alias PN importati da {yaml_file} — inseriti: {inserted}, aggiornati: {updated}[/green]"
    )


def _build_norm_mpn_index(db: Session) -> dict[str, int]:
    from .pn import normalize_pn

    rows = db.execute(
        select(Product.id, Product.mpn).where(Product.mpn.is_not(None))
    ).all()
    norm_to_product: dict[str, int] = {}
    for pid, mpn in rows:
        try:
            key = normalize_pn(str(mpn))
        except Exception:
            continue
        if key:
            norm_to_product[key] = int(pid)
    return norm_to_product


def _apply_pn_alias_blocks(
    db: Session,
    data: list[AliasBlock],
    norm_to_product: dict[str, int],
) -> tuple[int, int]:
    from .pn import normalize_pn

    inserted = 0
    updated = 0
    for block in data:
        dealer = _dealer_from_block(block)
        block_inserted, block_updated = _apply_aliases_for_block(
            db, dealer, block.get("aliases") or [], norm_to_product, normalize_pn
        )
        inserted += block_inserted
        updated += block_updated
    db.commit()
    return inserted, updated


def _dealer_from_block(block: AliasBlock) -> str | None:
    dealer_raw = block.get("dealer")
    dealer = str(dealer_raw or "").strip()
    return dealer or None


def _apply_aliases_for_block(
    db: Session,
    dealer: str | None,
    aliases: list[AliasEntry],
    norm_to_product: dict[str, int],
    normalize_pn,
) -> tuple[int, int]:
    inserted = 0
    updated = 0
    for alias in aliases:
        maker_norm, dealer_norm = _normalized_alias_codes(alias, normalize_pn)
        if not maker_norm:
            continue
        target_id = norm_to_product.get(maker_norm)
        if not target_id:
            continue
        row = _find_existing_alias_row(db, dealer, dealer_norm)
        confidence = _alias_confidence(alias)
        if row:
            _update_alias_row(row, target_id, maker_norm, confidence)
            updated += 1
        else:
            _insert_alias_row(
                db, dealer, target_id, maker_norm, dealer_norm, confidence
            )
            inserted += 1
    return inserted, updated


def _normalized_alias_codes(alias: AliasEntry, normalize_pn) -> tuple[str, str | None]:
    maker = normalize_pn(str(alias.get("maker_pn") or ""))
    dealer_pn = str(alias.get("dealer_pn") or "").strip()
    dealer_norm = normalize_pn(dealer_pn) if dealer_pn else None
    return maker, dealer_norm


def _find_existing_alias_row(db: Session, dealer: str | None, dealer_norm: str | None):
    return db.scalar(
        select(PNMapping).where(
            PNMapping.dealer == dealer,
            PNMapping.dealer_pn_norm == dealer_norm,
        )
    )


def _alias_confidence(alias: AliasEntry) -> float:
    conf_raw = alias.get("confidence")
    return float(conf_raw) if conf_raw is not None else 1.0


def _update_alias_row(
    row: PNMapping, target_id: int, maker_norm: str, confidence: float
) -> None:
    row.product_id = int(target_id)
    row.maker_pn_norm = maker_norm
    row.confidence = confidence


def _insert_alias_row(
    db: Session,
    dealer: str | None,
    target_id: int,
    maker_norm: str,
    dealer_norm: str | None,
    confidence: float,
) -> None:
    db.add(
        PNMapping(
            product_id=int(target_id),
            dealer=dealer,
            maker_pn_norm=maker_norm,
            dealer_pn_norm=dealer_norm,
            confidence=confidence,
        )
    )


@app.command("fetch-policy")
def fetch_policy(
    dealer: str = typer.Option(..., help="Dealer name"),
    url: str = typer.Option(..., help="URL pagina Spedizioni/Condizioni"),
    header: list[str] = typer.Option(None, help="extra HTTP headers (key:value)"),
) -> None:
    """Fetch a shipping policy page and upsert DealerPolicy using deterministic rules."""
    import httpx

    hdrs = _build_headers_from_cli(header)
    create_all()
    with httpx.Client(
        timeout=15.0,
        headers=hdrs or {"User-Agent": "BikeCopilotBot/0.1"},
        follow_redirects=True,
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        ext = parse_policy_html(r.text)
    with SessionLocal() as db:
        _upsert_dealer_policy(db, dealer, ext)
    rich.print(
        {
            "dealer": dealer,
            "base_cost": ext.base_cost,
            "free_threshold": ext.free_threshold,
            "lead_days_std": ext.lead_days_std,
            "confidence": ext.confidence,
        }
    )


def _upsert_dealer_policy(
    db: Session,
    dealer: str,
    ext,
) -> None:
    row = db.scalar(select(DealerPolicy).where(DealerPolicy.dealer == dealer))
    if row is None:
        db.add(
            DealerPolicy(
                dealer=dealer,
                base_cost=ext.base_cost,
                free_threshold=ext.free_threshold,
                lead_days_std=ext.lead_days_std,
                source="rules",
                confidence=ext.confidence,
            )
        )
    else:
        row.base_cost = ext.base_cost
        row.free_threshold = ext.free_threshold
        row.lead_days_std = ext.lead_days_std
        row.source = "rules"
        row.confidence = ext.confidence
    db.commit()


@app.command("ingest-csv")
def ingest_csv(
    products: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="products.csv",
    ),
    offers: Path = typer.Option(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="offers.csv",
    ),
) -> None:
    """Ingest demo CSVs with staging and upsert."""
    ps = parse_products_csv(products)
    os_list = parse_offers_csv(offers)
    stats: IngestStats = upsert(ps, os_list)
    rich.print(stats)


@app.command("ingest-pdf")
def ingest_pdf(
    pdf: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    mapping: Path | None = typer.Option(
        None, exists=False, help="Provider mapping YAML"
    ),
    provider: str = typer.Option("PDFProvider"),
) -> None:
    """Extract tables from PDF and upsert using a mapping file."""
    products, offers = extract_from_pdf(pdf, mapping)
    stats: IngestStats = upsert(products, offers)
    rich.print(stats)


@app.command("fetch-web")
def fetch_web(
    html: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
) -> None:
    """Parse a local HTML file with a mapping YAML and upsert results."""
    products, offers = parse_web_file(html, mapping)
    stats: IngestStats = upsert(products, offers)
    rich.print(stats)


@app.command("fetch-web-url")
def fetch_web_url(
    url: list[str] = typer.Option(
        ..., help="one or more URLs to fetch", rich_help_panel="Web"
    ),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    follow_next: bool = typer.Option(False, help="follow pagination.next links"),
    max_pages: int = typer.Option(3, min=1, help="max pages to fetch per seed"),
    delay: float = typer.Option(
        0.5, min=0.0, help="delay (seconds) between page fetches"
    ),
    header: list[str] = typer.Option(
        None,
        help='extra HTTP headers (key:value), e.g. "Cookie: a=b"',
    ),
) -> None:
    """Fetch remote pages and upsert parsed products/offers using mapping YAML."""
    hdrs = _build_headers_from_cli(header)
    stats = _fetch_and_ingest_web(url, mapping, follow_next, max_pages, delay, hdrs)
    rich.print(stats)


def _fetch_and_ingest_web(
    urls: list[str],
    mapping: Path,
    follow_next: bool,
    max_pages: int,
    delay: float,
    headers: dict[str, str],
) -> IngestStats:
    products, offers = fetch_and_parse_urls(
        urls=urls,
        mapping_yaml=mapping,
        follow_next=follow_next,
        max_pages=max_pages,
        delay_sec=delay,
        headers=headers,
    )
    return upsert(products, offers)


@app.command("search-web")
def search_web(
    query: str = typer.Option(..., help="search query to embed in url_template"),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    follow_next: bool = typer.Option(True, help="follow pagination.next links"),
    max_pages: int = typer.Option(5, min=1, help="max pages to fetch"),
    delay: float = typer.Option(
        0.5, min=0.0, help="delay (seconds) between page fetches"
    ),
) -> None:
    """Search a site using mapping.search.url_template and ingest parsed results."""
    urls = build_search_urls(query, mapping)
    products, offers = fetch_and_parse_urls(
        urls=urls,
        mapping_yaml=mapping,
        follow_next=follow_next,
        max_pages=max_pages,
        delay_sec=delay,
        headers=None,
    )
    stats: IngestStats = upsert(products, offers)
    rich.print({"urls": urls, **stats.__dict__})


@app.command("fetch-sitemap")
def fetch_sitemap(
    sitemap: str = typer.Option(..., help="sitemap or sitemap index URL"),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    contains: str = typer.Option(
        "/prodotto/",
        help="only visit URLs containing this substring (e.g., '/prodotto/')",
    ),
    limit: int = typer.Option(0, help="max URLs to visit (0 = no limit)"),
    delay: float = typer.Option(0.5, min=0.0, help="delay between requests"),
    header: list[str] = typer.Option(
        None,
        help='extra HTTP headers (key:value), e.g. "Cookie: a=b"',
    ),
) -> None:
    """Fetch all product detail pages listed in a sitemap and ingest offers."""
    hdrs = _build_headers_from_cli(header)
    urls = _sitemap_target_urls(sitemap, hdrs, contains, limit)
    products, offers = _fetch_sitemap_details(urls, mapping, hdrs, delay)
    stats: IngestStats = upsert(products, offers)
    rich.print({"visited": len(urls), **stats.__dict__})


def _sitemap_target_urls(
    sitemap: str,
    headers: dict[str, str],
    contains: str,
    limit: int,
) -> list[str]:
    urls = parse_sitemap_urls(sitemap, headers=headers, limit=(limit or None))
    return [u for u in urls if contains in u]


def _fetch_sitemap_details(
    urls: list[str],
    mapping: Path,
    headers: dict[str, str],
    delay: float,
):
    from time import sleep
    from .adapters.web_adapter import _load_mapping  # type: ignore
    from .types import ProductInput
    import httpx

    mapping_obj = _load_mapping(mapping)
    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    seen: set[tuple[str, str, str]] = set()
    with httpx.Client(
        timeout=10.0,
        headers=headers or {"User-Agent": "BikeCopilotBot/0.1"},
        follow_redirects=True,
    ) as client:
        for u in urls:
            _fetch_single_sitemap_url(
                client, u, mapping_obj, seen, products, offers, delay, sleep
            )
    return products, offers


def _fetch_single_sitemap_url(
    client,
    url: str,
    mapping_obj,
    seen: set[tuple[str, str, str]],
    products,
    offers,
    delay: float,
    sleep,
) -> None:
    try:
        r = client.get(url)
        r.raise_for_status()
        from .adapters.web_adapter import parse_detail_html  # type: ignore

        p, o = parse_detail_html(r.text, mapping_obj)
        if p and o:
            key = (p.brand, p.mpn, o.supplier)
            if key in seen:
                return
            seen.add(key)
            products.append(p)
            offers.append(o)
    except Exception:
        return
    finally:
        sleep(max(0.0, delay))


@app.command("ingest-csv-mapped")
def ingest_csv_mapped(
    csv: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
) -> None:
    """Ingest a single CSV using a mapping YAML to canonical fields."""
    products, offers = parse_unified_csv(csv, mapping)
    stats: IngestStats = upsert(products, offers)
    rich.print(stats)


@app.command("reset-db")
def reset_db() -> None:
    """Delete local SQLite database and recreate tables."""
    from .config import settings

    url = settings.db_url
    if url.startswith("sqlite"):
        path = url.split("///")[-1]
        for p in [path, f"{path}-shm", f"{path}-wal"]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
    # Recreate
    create_all()
    rich.print({"db": "reset", "url": url})


@app.command("ingest-csv-synth")
def ingest_csv_synth(
    csv: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    suppliers: int = typer.Option(
        3, min=1, help="number of synthetic suppliers per product (approx)"
    ),
    coverage: float = typer.Option(
        0.6, min=0.0, max=1.0, help="fraction of products that get extra suppliers"
    ),
    jitter: float = typer.Option(
        0.12, min=0.0, max=0.5, help="max price variation +/- as fraction"
    ),
) -> None:
    """Ingest CSV and synthesize duplicate offers across multiple suppliers."""
    base_products, base_offers = parse_unified_csv(csv, mapping)

    stats = upsert(base_products, base_offers)
    rng = random.Random(42)
    grouped = _group_offers_by_product(base_offers)
    extra_offers = _generate_synthetic_offers(grouped, suppliers, coverage, jitter, rng)
    stats = _upsert_synthetic_offers(extra_offers, stats)
    summary = _compute_synth_summary()
    rich.print({**summary, "ingest": stats.__dict__})


def _group_offers_by_product(
    base_offers: list["OfferInput"],
) -> dict[tuple[str, str], dict[str, float]]:
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for offer in base_offers:
        key = (offer.brand, offer.mpn)
        grouped[key] = {"price": offer.price}
    return grouped


def _generate_synthetic_offers(
    grouped: dict[tuple[str, str], dict[str, float]],
    suppliers: int,
    coverage: float,
    jitter: float,
    rng: random.Random,
) -> list[OfferInput]:
    supplier_names = _synthetic_supplier_names()
    extra_offers: list[OfferInput] = []
    for (brand, mpn), info in grouped.items():
        base_price = float(info.get("price", 0.0)) or 0.0
        if not _should_synthesize_group(base_price, coverage, rng):
            continue
        extra_offers.extend(
            _offers_for_group(
                brand,
                mpn,
                base_price,
                suppliers,
                jitter,
                rng,
                supplier_names,
            )
        )
    return extra_offers


def _synthetic_supplier_names() -> list[str]:
    return [
        "BiciPro",
        "RideLabs",
        "PedalX",
        "Velocita",
        "GearHub",
        "TrailWorks",
        "WheelHouse",
        "ChainLine",
    ]


def _should_synthesize_group(
    base_price: float,
    coverage: float,
    rng: random.Random,
) -> bool:
    if rng.random() > coverage:
        return False
    if base_price <= 0:
        return False
    return True


def _offers_for_group(
    brand: str,
    mpn: str,
    base_price: float,
    suppliers: int,
    jitter: float,
    rng: random.Random,
    supplier_names: list[str],
) -> list[OfferInput]:
    extra_count = max(0, suppliers - 1)
    chosen = rng.sample(supplier_names, k=min(extra_count, len(supplier_names)))
    offers: list[OfferInput] = []
    for sup in chosen:
        price = _synthetic_price(base_price, jitter, rng)
        in_stock = rng.random() < 0.7
        lead = rng.randint(0, 5)
        offers.append(
            OfferInput(
                brand=brand,
                mpn=mpn,
                supplier=sup,
                price=price,
                in_stock=in_stock,
                lead_time_days=lead,
            )
        )
    return offers


def _synthetic_price(base_price: float, jitter: float, rng: random.Random) -> float:
    delta = rng.uniform(-jitter, jitter)
    return round(base_price * (1.0 + delta), 2)


def _upsert_synthetic_offers(extra_offers, stats: IngestStats) -> IngestStats:
    if not extra_offers:
        return stats
    stats2 = upsert([], extra_offers)
    return IngestStats(
        products_new=stats.products_new,
        products_updated=stats.products_updated,
        offers_upserted=stats.offers_upserted + stats2.offers_upserted,
        offers_skipped=stats.offers_skipped + stats2.offers_skipped,
    )


def _compute_synth_summary() -> dict[str, int]:
    with SessionLocal() as db:
        prod_count = int(
            db.scalar(select(func.count(func.distinct(SupplierOffer.product_id)))) or 0
        )
        offer_count = int(db.scalar(select(func.count(SupplierOffer.id))) or 0)
        sup_count = int(
            db.scalar(select(func.count(func.distinct(SupplierOffer.supplier)))) or 0
        )
        in_stock = int(
            db.scalar(
                select(func.count(SupplierOffer.id)).where(SupplierOffer.in_stock)
            )
            or 0
        )
    return {
        "products": prod_count,
        "offers": offer_count,
        "suppliers": sup_count,
        "in_stock_offers": in_stock,
    }


@app.command()
def search_cli(
    query: str | None = typer.Option(None, help="free text"),
    speed: str | None = typer.Option(None),
    freehub: Freehub | None = typer.Option(None, case_sensitive=False),
    brake: Brake | None = typer.Option(None, case_sensitive=False),
    axle: str | None = typer.Option(None),
    rotor: Rotor | None = typer.Option(None, case_sensitive=False),
    budget_max: float | None = typer.Option(None),
) -> None:
    """Search offers and render a table with top 3 results."""
    req = _build_search_request(query, speed, freehub, brake, axle, rotor, budget_max)
    res = search(req)
    table = _build_search_table(res.items)
    rich.print(table)


def _build_search_request(
    query: str | None,
    speed: str | None,
    freehub: Freehub | None,
    brake: Brake | None,
    axle: str | None,
    rotor: Rotor | None,
    budget_max: float | None,
) -> SearchRequest:
    return SearchRequest(
        query_text=query,
        speed=speed,
        freehub=freehub,
        brake=brake,
        axle=axle,
        rotor=rotor,
        budget_max=budget_max,
    )


def _build_search_table(items) -> Table:
    table = Table(title="Top 3 Offers")
    for col in (
        "offer_id",
        "brand",
        "mpn",
        "supplier",
        "price",
        "stock",
        "lead",
        "score",
    ):
        table.add_column(col)
    for it in items:
        table.add_row(
            str(it.id),
            it.brand,
            it.mpn,
            it.supplier,
            f"{it.price:.2f}",
            "yes" if it.in_stock else "no",
            str(it.lead_time_days or "-"),
            f"{it.score:.3f}",
        )
    return table


@app.command()
def quote_cli(
    offer_id: int = typer.Option(..., autocompletion=_offer_id_completions),
    qty: int = typer.Option(1, min=1),
    customer_name: str = typer.Option(...),
    customer_contact: str = typer.Option(...),
    validity_days: int = typer.Option(7),
    notes: str | None = typer.Option(None),
) -> None:
    """Render a quote for an existing offer (single-line) and print artifact paths."""
    with SessionLocal() as db:
        offer = _require_offer(db, offer_id)
        context = _build_single_line_quote_context(
            offer,
            qty,
            customer_name,
            customer_contact,
            validity_days,
            notes,
        )
        html_path, pdf_path = render_quote(context)
        _log_cli_quote(db, offer.id, pdf_path)
        out = QuoteResponse(
            content_type="application/pdf" if pdf_path else "text/html",
            html_path=html_path,
            pdf_path=pdf_path,
        )
        rich.print(out.model_dump())


from sqlalchemy.orm import Session


def _require_offer(db: Session, offer_id: int) -> SupplierOffer:
    offer = db.get(SupplierOffer, offer_id)
    if offer is None:
        typer.secho("offer_id not found", fg=typer.colors.RED)
        raise typer.Exit(code=2)
    return offer


def _build_single_line_quote_context(
    offer: SupplierOffer,
    qty: int,
    customer_name: str,
    customer_contact: str,
    validity_days: int,
    notes: str | None,
) -> dict[str, object]:
    product = offer.product
    return {
        "customer_name": customer_name,
        "customer_contact": customer_contact,
        "validity_days": validity_days,
        "notes": notes,
        "items": [
            {
                "brand": product.brand,
                "mpn": product.mpn,
                "name": product.name,
                "supplier": offer.supplier,
                "price": offer.price,
                "qty": int(qty),
                "in_stock": offer.in_stock,
                "lead_time_days": offer.lead_time_days,
            }
        ],
    }


def _log_cli_quote(
    db: Session,
    offer_id: int,
    pdf_path: str | None,
) -> None:
    db.add(
        EventLog(
            type="quote_created",
            payload={"offer_id": offer_id, "cli": True, "pdf": bool(pdf_path)},
        )
    )
    db.commit()


@app.command()
def health() -> None:
    from shutil import which
    from . import __version__

    info = {
        "status": "ok",
        "db": True,
        "pdfkit": bool(which("wkhtmltopdf")),
        "version": __version__,
    }
    rich.print(info)


@app.command()
def ui(port: int = typer.Option(7860), host: str = typer.Option("0.0.0.0")) -> None:
    from .ui import build_interface

    iface = build_interface()
    iface.launch(server_name=host, server_port=port)


@app.command()
def api(port: int = typer.Option(8000), host: str = typer.Option("0.0.0.0")) -> None:
    import uvicorn

    uvicorn.run("app.api:app", host=host, port=port, reload=False)


def _env_value(name: str | None) -> str:
    if not name:
        return ""
    return os.getenv(name, "").strip()


def _login_mode(cfg: DealerConfig) -> str | None:
    if cfg.login:
        return cfg.login.mode
    if cfg.auth.mode_env:
        mode = os.getenv(cfg.auth.mode_env, "").strip().lower()
        return mode or None
    return None


class DealerSession:
    def __init__(self, client: httpx.Client, login_cfg: DealerLoginConfig | None):
        self.client = client
        self.login_cfg = login_cfg

    def close(self) -> None:
        self.client.close()


def _build_dealer_session(cfg: DealerConfig) -> DealerSession:
    client = _build_http_client()
    mode = _login_mode(cfg)
    username = _env_value(cfg.auth.username_env)
    password = _env_value(cfg.auth.password_env)
    cookie = _env_value(cfg.auth.cookie_env)

    if mode == "cookie":
        _apply_cookie_auth(client, cfg, cookie)
    elif mode == "basic":
        _apply_basic_auth(client, cfg, username, password)
    elif mode == "form":
        _perform_form_login(client, cfg, username, password)
    elif mode == "spa":
        _perform_spa_login(client, cfg, username, password)
    return DealerSession(client, cfg.login)


def _build_http_client() -> httpx.Client:
    headers = {"User-Agent": "BikeCopilotBot/0.1"}
    return httpx.Client(timeout=15.0, headers=headers, follow_redirects=True)


def _apply_cookie_auth(
    client: httpx.Client, cfg: DealerConfig, cookie: str | None
) -> None:
    if not cookie:
        raise typer.BadParameter(
            f"Nessun cookie impostato per {cfg.name}; definisci {cfg.auth.cookie_env}."
        )
    client.headers["Cookie"] = cookie


def _apply_basic_auth(
    client: httpx.Client,
    cfg: DealerConfig,
    username: str | None,
    password: str | None,
) -> None:
    if not username or not password:
        raise typer.BadParameter(
            f"Credenziali mancanti per {cfg.name}; definisci {cfg.auth.username_env} e {cfg.auth.password_env}."
        )
    client.auth = (username, password)  # type: ignore[assignment]


def _require_login_cfg(cfg: DealerConfig) -> DealerLoginConfig:
    if not cfg.login:
        raise typer.BadParameter(
            f"Configurazione login mancante per {cfg.name} (section login in providers/dealers.yaml)."
        )
    if not cfg.login.url:
        raise typer.BadParameter(f"login.url non impostato per {cfg.name}.")
    return cfg.login


def _perform_preflight(
    client: httpx.Client, cfg: DealerConfig, login_cfg: DealerLoginConfig
) -> None:
    if not login_cfg.preflight_url:
        return
    pre_resp = client.get(login_cfg.preflight_url)
    if pre_resp.status_code >= 400:
        raise typer.BadParameter(
            f"Preflight fallito per {cfg.name}: HTTP {pre_resp.status_code}"
        )
    client.headers["Referer"] = login_cfg.preflight_url


def _perform_form_login(
    client: httpx.Client,
    cfg: DealerConfig,
    username: str | None,
    password: str | None,
) -> None:
    login_cfg = _require_login_cfg(cfg)
    _ensure_credentials(cfg, username, password)
    _perform_preflight(client, cfg, login_cfg)

    payload_items = _build_login_payload_items(login_cfg, username or "", password or "")
    resp = _submit_form_login_request(client, cfg, login_cfg, payload_items)
    if resp.status_code >= 400:
        raise typer.BadParameter(
            f"Login fallito per {cfg.name}: HTTP {resp.status_code}"
        )


def _ensure_credentials(
    cfg: DealerConfig, username: str | None, password: str | None
) -> None:
    if not username or not password:
        raise typer.BadParameter(
            f"Credenziali mancanti per {cfg.name}; definisci {cfg.auth.username_env} e {cfg.auth.password_env}."
        )


def _build_login_payload_items(
    login_cfg: DealerLoginConfig, username: str, password: str
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = list((login_cfg.extra_fields or {}).items())
    user_field = login_cfg.username_field or ""
    pass_field = login_cfg.password_field or ""
    if user_field:
        items.append((user_field, username))
    if pass_field:
        items.append((pass_field, password))
    return items


def _submit_form_login_request(
    client: httpx.Client,
    cfg: DealerConfig,
    login_cfg: DealerLoginConfig,
    payload_items: list[tuple[str, str]],
):
    method = (login_cfg.method or "POST").upper()
    url = login_cfg.url or ""
    if method == "POST":
        encoding = (login_cfg.encoding or "form").lower()
        if encoding == "multipart":
            files = [(k, (None, v)) for k, v in payload_items]
            return client.post(url, files=files)
        form_data = dict(payload_items)
        return client.post(url, data=form_data)
    if method == "GET":
        query_params = dict(payload_items)
        return client.get(url, params=query_params)
    raise typer.BadParameter(f"Metodo login {method} non supportato per {cfg.name}.")


def _perform_spa_login(
    client: httpx.Client,
    cfg: DealerConfig,
    username: str | None,
    password: str | None,
) -> None:
    login_cfg = _require_login_cfg(cfg)
    _ensure_credentials(cfg, username, password)
    _perform_preflight(client, cfg, login_cfg)

    payload = _build_spa_payload(login_cfg, username or "", password or "")
    resp = _submit_spa_login_request(client, login_cfg, payload)
    if resp.status_code >= 400:
        raise typer.BadParameter(
            f"Login SPA fallito per {cfg.name}: HTTP {resp.status_code}"
        )

    token = _extract_spa_token(resp)
    if token:
        client.headers["Authorization"] = f"Bearer {token}"


def _build_spa_payload(
    login_cfg: DealerLoginConfig,
    username: str,
    password: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = dict(login_cfg.extra_fields or {})
    if login_cfg.username_field:
        payload[login_cfg.username_field] = username
    if login_cfg.password_field:
        payload[login_cfg.password_field] = password
    return payload


def _submit_spa_login_request(
    client: httpx.Client,
    login_cfg: DealerLoginConfig,
    payload: dict[str, Any],
):
    client.headers["Content-Type"] = "application/json"
    url = login_cfg.url or ""
    return client.post(url, json=payload)


def _extract_spa_token(resp: httpx.Response) -> str | None:
    try:
        auth_data = resp.json()
    except ValueError:
        # Non-JSON response: fall back to cookies/session state.
        return None
    if not isinstance(auth_data, dict):
        # Unexpected JSON shape: do not fail dealer sync; just skip token extraction.
        return None
    token = auth_data.get("token") or auth_data.get("access_token")
    if isinstance(token, str) and token:
        return token
    return None


@app.command(
    "dealer-sync",
    help="Sincronizza un dealer usando providers/dealers.yaml (policy + catalogo).",
)
def dealer_sync(
    dealer: str = typer.Argument(..., help="Dealer key o nome (es. ciclodiffusione)"),
    mode: str = typer.Option(
        "all", help="Modalità: policy, catalogo o all", case_sensitive=False
    ),
    max_pages: int = typer.Option(
        50, min=1, help="Max pagine da seguire per seed (solo web)"
    ),
    delay: float = typer.Option(
        0.5, min=0.0, help="Delay (secondi) tra richieste web (solo web)"
    ),
) -> None:
    mode_l = mode.strip().lower()
    cfg = _require_dealer_cfg(dealer)
    _print_dealer_intro(cfg)

    from .dealers import _repo_root

    mapping_path = _repo_root() / cfg.mapping if cfg.mapping else None

    session = _build_dealer_session(cfg)
    try:
        _sync_dealer_policy_if_needed(cfg, mode_l, session)
        _sync_dealer_catalog_if_needed(
            cfg, mode_l, session, max_pages, delay, mapping_path
        )
    finally:
        session.close()


def _require_dealer_cfg(dealer: str) -> DealerConfig:
    cfg = find_dealer(dealer)
    if cfg is None:
        raise typer.BadParameter(
            f"Dealer '{dealer}' non trovato in providers/dealers.yaml"
        )
    return cfg


def _print_dealer_intro(cfg: DealerConfig) -> None:
    rich.print(
        f"[bold]Dealer[/bold]: {cfg.name} (tipo={cfg.type}, platform={cfg.platform})"
    )


def _sync_dealer_policy_if_needed(
    cfg: DealerConfig, mode_l: str, session: DealerSession
) -> None:
    if mode_l not in ("all", "policy") or not cfg.policy_url:
        return
    rich.print(f"[cyan]Scarico policy da[/cyan] {cfg.policy_url}")
    r = session.client.get(cfg.policy_url)
    r.raise_for_status()
    ext = parse_policy_html(r.text)
    create_all()
    with SessionLocal() as db:
        _upsert_dealer_policy(db, cfg.name, ext)
    rich.print(
        {
            "dealer": cfg.name,
            "base_cost": ext.base_cost,
            "free_threshold": ext.free_threshold,
            "lead_days_std": ext.lead_days_std,
            "confidence": ext.confidence,
        }
    )


def _sync_dealer_catalog_if_needed(
    cfg: DealerConfig,
    mode_l: str,
    session: DealerSession,
    max_pages: int,
    delay: float,
    mapping_path: Path | None,
) -> None:
    if not _can_sync_catalog(cfg, mode_l, mapping_path):
        return
    from .adapters.web_adapter import (
        fetch_and_parse_urls,
        parse_sitemap_urls,
    )

    urls = _collect_dealer_urls(cfg, session, parse_sitemap_urls)
    if not urls:
        rich.print(
            "[yellow]Nessun URL seed configurato per il dealer; salta ingest catalogo.[/yellow]"
        )
        return
    if mapping_path is None:
        raise typer.BadParameter("Path mapping mancante per ingest catalogo")
    _run_dealer_catalog_ingest(
        cfg, urls, mapping_path, session, max_pages, delay, fetch_and_parse_urls
    )


def _can_sync_catalog(
    cfg: DealerConfig,
    mode_l: str,
    mapping_path: Path | None,
) -> bool:
    if mode_l not in ("all", "catalogo"):
        return False
    if cfg.type != "web":
        rich.print(
            f"[yellow]Tipo '{cfg.type}' non ancora supportato per ingest automatico[/yellow]"
        )
        return False
    if not cfg.mapping or mapping_path is None:
        rich.print(
            "[yellow]Nessun mapping configurato per questo dealer (campo 'mapping' mancante).[/yellow]"
        )
        return False
    return True


def _run_dealer_catalog_ingest(
    cfg: DealerConfig,
    urls: list[str],
    mapping_path: Path,
    session: DealerSession,
    max_pages: int,
    delay: float,
    fetch_and_parse_urls,
) -> None:
    rich.print(f"[cyan]Ingest catalogo[/cyan] da {len(urls)} seed")

    products, offers = fetch_and_parse_urls(
        urls=urls,
        mapping_yaml=mapping_path,
        follow_next=True,
        max_pages=max_pages,
        delay_sec=delay,
        headers=None,
        session=session.client,
        progress_cb=_dealer_progress_cb,
    )
    stats: IngestStats = upsert(products, offers)
    rich.print(
        {
            "dealer": cfg.name,
            "products_new": stats.products_new,
            "products_updated": stats.products_updated,
            "offers_upserted": stats.offers_upserted,
            "offers_skipped": stats.offers_skipped,
        }
    )


def _collect_dealer_urls(
    cfg: DealerConfig,
    session: DealerSession,
    parse_sitemap_urls,
) -> list[str]:
    urls: list[str] = []
    urls.extend(cfg.seeds.urls)
    if cfg.seeds.sitemap:
        rich.print(f"[cyan]Leggo sitemap[/cyan] {cfg.seeds.sitemap}")
        more = parse_sitemap_urls(
            cfg.seeds.sitemap,
            headers=None,
            limit=None,
            session=session.client,
        )
        urls.extend(more)
    return urls


def _dealer_progress_cb(
    page_url: str,
    page_idx: int,
    products_total: int,
    offers_total: int,
) -> None:
    parsed = urlparse(page_url)
    params = parse_qs(parsed.query or "")
    page_hint = params.get("page", [""])[0] or params.get("skip", [""])[0]
    label = page_hint or str(page_idx)
    location = parsed.path or page_url
    rich.print(
        f"[dim]  ↳ pagina {label} ({location}) "
        f"prodotti={products_total} offerte={offers_total}[/dim]"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
