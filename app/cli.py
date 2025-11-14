from __future__ import annotations

from pathlib import Path

import rich
from pydantic import BaseModel
import typer
from rich.table import Table
import os
import random
import httpx

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
from .types import Brake, Freehub, QuoteResponse, Rotor, SearchRequest
from .policy import parse_policy_html
from .models import DealerPolicy
from .dealers import DealerConfig, DealerLoginConfig, find_dealer


app = typer.Typer(add_completion=True, no_args_is_help=True, help="Bike Copilot CLI")


def _offer_id_completions(incomplete: str) -> list[str]:
    create_all()
    with SessionLocal() as db:
        rows: list[tuple[int, str, str, str, float]] = [
            (o.id, o.product.brand, o.product.mpn, o.supplier, float(o.price))
            for o in db.query(SupplierOffer).all()
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
) -> list[tuple[SupplierOffer, str, float, bool, int | None, str, str, str, str | None]]:
    from sqlalchemy import asc

    with SessionLocal() as db:
        q = db.query(
            SupplierOffer,
            SupplierOffer.supplier,
            SupplierOffer.price,
            SupplierOffer.in_stock,
            SupplierOffer.lead_time_days,
            Product.brand,
            Product.mpn,
            Product.name,
            Product.category,
        ).join(Product, SupplierOffer.product_id == Product.id)
        if supplier:
            q = q.filter(SupplierOffer.supplier == supplier)
        if brand:
            q = q.filter(Product.brand == brand)
        if category:
            q = q.filter(Product.category == category)
        q = q.order_by(
            asc(Product.brand), asc(Product.mpn), asc(SupplierOffer.supplier)
        )
        if isinstance(limit, int) and limit > 0:
            q = q.limit(limit)
        rows = q.all()
    return rows


def _build_export_rows(
    rows: list[tuple[SupplierOffer, str, float, bool, int | None, str, str, str, str | None]]
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


def _build_norm_mpn_index(db: SessionLocal) -> dict[str, int]:
    from .pn import normalize_pn

    rows = db.query(Product.id, Product.mpn).filter(Product.mpn.isnot(None)).all()
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
    db: SessionLocal,
    data: list[dict[str, object]],
    norm_to_product: dict[str, int],
) -> tuple[int, int]:
    from .pn import normalize_pn

    inserted = 0
    updated = 0
    for block in data:
        dealer = str(block.get("dealer") or "").strip() or None  # type: ignore[union-attr]
        aliases = block.get("aliases", []) or []  # type: ignore[assignment]
        for a in aliases:  # type: ignore[assignment]
            maker = normalize_pn(str(a.get("maker_pn") or ""))  # type: ignore[call-arg]
            dealer_pn = str(a.get("dealer_pn") or "").strip()  # type: ignore[call-arg]
            dealer_norm = normalize_pn(dealer_pn) if dealer_pn else None
            if not maker:
                continue
            target_id = norm_to_product.get(maker)
            if not target_id:
                continue
            q = db.query(PNMapping).filter(
                PNMapping.dealer == dealer,
                PNMapping.dealer_pn_norm == dealer_norm,
            )
            row = q.first()
            conf = float(a.get("confidence") or 1.0)  # type: ignore[call-arg]
            if row:
                row.product_id = int(target_id)
                row.maker_pn_norm = maker
                row.confidence = conf
                updated += 1
            else:
                db.add(
                    PNMapping(
                        product_id=int(target_id),
                        dealer=dealer,
                        maker_pn_norm=maker,
                        dealer_pn_norm=dealer_norm,
                        confidence=conf,
                    )
                )
                inserted += 1
    db.commit()
    return inserted, updated


@app.command("fetch-policy")
def fetch_policy(
    dealer: str = typer.Option(..., help="Dealer name"),
    url: str = typer.Option(..., help="URL pagina Spedizioni/Condizioni"),
    header: list[str] = typer.Option(None, help="extra HTTP headers (key:value)"),
) -> None:
    """Fetch a shipping policy page and upsert DealerPolicy using deterministic rules."""
    import httpx

    hdrs: dict[str, str] = {}
    for h in header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            hdrs[k.strip()] = v.strip()
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
        row = db.query(DealerPolicy).filter(DealerPolicy.dealer == dealer).first()
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
    rich.print(
        {
            "dealer": dealer,
            "base_cost": ext.base_cost,
            "free_threshold": ext.free_threshold,
            "lead_days_std": ext.lead_days_std,
            "confidence": ext.confidence,
        }
    )


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
    """Fetch remote pages and upsert parsed products/offers using mapping YAML.

    For dynamic JS sites, consider saving HTML and using fetch-web instead, or add a headless step later.
    """
    hdrs: dict[str, str] = {}
    if header:
        for h in header:
            if ":" in h:
                k, v = h.split(":", 1)
                hdrs[k.strip()] = v.strip()
    products, offers = fetch_and_parse_urls(
        urls=url,
        mapping_yaml=mapping,
        follow_next=follow_next,
        max_pages=max_pages,
        delay_sec=delay,
        headers=hdrs,
    )
    stats: IngestStats = upsert(products, offers)
    rich.print(stats)


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
    """Fetch all product detail pages listed in a sitemap and ingest offers.

    Designed for WooCommerce sites that expose product URLs in sitemaps.
    """
    hdrs: dict[str, str] = {}
    if header:
        for h in header:
            if ":" in h:
                k, v = h.split(":", 1)
                hdrs[k.strip()] = v.strip()
    urls = [
        u
        for u in parse_sitemap_urls(sitemap, headers=hdrs, limit=(limit or None))
        if contains in u
    ]
    # Fetch sequentially with delay using detail parsing path
    from time import sleep
    from .adapters.web_adapter import parse_detail_html, _load_mapping  # type: ignore
    from .types import ProductInput, OfferInput
    import httpx

    mapping_obj = _load_mapping(mapping)
    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    seen: set[tuple[str, str, str]] = set()
    with httpx.Client(
        timeout=10.0,
        headers=hdrs or {"User-Agent": "BikeCopilotBot/0.1"},
        follow_redirects=True,
    ) as client:
        for u in urls:
            try:
                r = client.get(u)
                r.raise_for_status()
                p, o = parse_detail_html(r.text, mapping_obj)
                if p and o:
                    key = (p.brand, p.mpn, o.supplier)
                    if key in seen:
                        continue
                    seen.add(key)
                    products.append(p)
                    offers.append(o)
            except Exception:
                continue
            finally:
                sleep(max(0.0, delay))
    stats: IngestStats = upsert(products, offers)
    rich.print({"visited": len(urls), **stats.__dict__})


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
    from .types import OfferInput

    base_products, base_offers = parse_unified_csv(csv, mapping)

    # Upsert base rows first
    stats = upsert(base_products, base_offers)

    # Generate synthetic suppliers
    supplier_names = [
        "BiciPro",
        "RideLabs",
        "PedalX",
        "Velocita",
        "GearHub",
        "TrailWorks",
        "WheelHouse",
        "ChainLine",
    ]
    rng = random.Random(42)

    # Build grouped products by (brand, mpn)
    grouped: dict[tuple[str, str], dict[str, str | float]] = {}
    for o in base_offers:
        key = (o.brand, o.mpn)
        grouped[key] = {"price": o.price}

    extra_offers: list[OfferInput] = []
    for (brand, mpn), info in grouped.items():
        if rng.random() > coverage:
            continue
        base_price = float(info.get("price", 0.0)) or 0.0
        if base_price <= 0:
            continue
        k = max(0, suppliers - 1)  # extra suppliers beyond the base
        chosen = rng.sample(supplier_names, k=min(k, len(supplier_names)))
        for sup in chosen:
            delta = rng.uniform(-jitter, jitter)
            price = round(base_price * (1.0 + delta), 2)
            in_stock = rng.random() < 0.7
            lead = rng.randint(0, 5)
            extra_offers.append(
                OfferInput(
                    brand=brand,
                    mpn=mpn,
                    supplier=sup,
                    price=price,
                    in_stock=in_stock,
                    lead_time_days=lead,
                )
            )

    if extra_offers:
        stats2 = upsert([], extra_offers)
        stats = IngestStats(
            products_new=stats.products_new,
            products_updated=stats.products_updated,
            offers_upserted=stats.offers_upserted + stats2.offers_upserted,
            offers_skipped=stats.offers_skipped + stats2.offers_skipped,
        )

    # Summary
    from sqlalchemy import func

    with SessionLocal() as db:
        prod_count = (
            db.query(func.count(SupplierOffer.product_id.distinct())).scalar() or 0
        )
        offer_count = db.query(func.count(SupplierOffer.id)).scalar() or 0
        sup_count = (
            db.query(func.count(SupplierOffer.supplier.distinct())).scalar() or 0
        )
        in_stock = (
            db.query(func.count(SupplierOffer.id))
            .filter(SupplierOffer.in_stock)
            .scalar()
            or 0
        )
    rich.print(
        {
            "products": prod_count,
            "offers": offer_count,
            "suppliers": sup_count,
            "in_stock_offers": in_stock,
            "ingest": stats.__dict__,
        }
    )


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
    req = SearchRequest(
        query_text=query,
        speed=speed,
        freehub=freehub,
        brake=brake,
        axle=axle,
        rotor=rotor,
        budget_max=budget_max,
    )
    res = search(req)
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
    for it in res.items:
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
    rich.print(table)


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
        offer = db.get(SupplierOffer, offer_id)
        if offer is None:
            typer.secho("offer_id not found", fg=typer.colors.RED)
            raise typer.Exit(code=2)
        product = offer.product
        context = {
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
        html_path, pdf_path = render_quote(context)
        db.add(
            EventLog(
                type="quote_created",
                payload={"offer_id": offer.id, "cli": True, "pdf": bool(pdf_path)},
            )
        )
        db.commit()
        out = QuoteResponse(
            content_type="application/pdf" if pdf_path else "text/html",
            html_path=html_path,
            pdf_path=pdf_path,
        )
        rich.print(out.model_dump())


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
    headers = {"User-Agent": "BikeCopilotBot/0.1"}
    mode = _login_mode(cfg)
    username = _env_value(cfg.auth.username_env)
    password = _env_value(cfg.auth.password_env)
    cookie = _env_value(cfg.auth.cookie_env)

    client = httpx.Client(
        timeout=15.0,
        headers=headers,
        follow_redirects=True,
    )

    if mode == "cookie":
        if not cookie:
            raise typer.BadParameter(
                f"Nessun cookie impostato per {cfg.name}; definisci {cfg.auth.cookie_env}."
            )
        client.headers["Cookie"] = cookie
    elif mode == "basic":
        if not username or not password:
            raise typer.BadParameter(
                f"Credenziali mancanti per {cfg.name}; definisci {cfg.auth.username_env} e {cfg.auth.password_env}."
            )
        client.auth = (username, password)  # type: ignore[assignment]
    elif mode == "form":
        if not cfg.login:
            raise typer.BadParameter(
                f"Configurazione login mancante per {cfg.name} (section login in providers/dealers.yaml)."
            )
        if not cfg.login.url:
            raise typer.BadParameter(
                f"login.url non impostato per {cfg.name}."
            )
        if not username or not password:
            raise typer.BadParameter(
                f"Credenziali mancanti per {cfg.name}; definisci {cfg.auth.username_env} e {cfg.auth.password_env}."
            )
        payload_items: list[tuple[str, str]] = list(cfg.login.extra_fields.items())
        if cfg.login.username_field:
            payload_items.append((cfg.login.username_field, username))
        if cfg.login.password_field:
            payload_items.append((cfg.login.password_field, password))

        method = (cfg.login.method or "POST").upper()
        if method == "POST":
            # For POST requests, send as form-encoded data
            form_data = dict(payload_items)
            resp = client.post(cfg.login.url, data=form_data)
        elif method == "GET":
            # For GET requests, use query parameters instead of form data
            query_params = dict(payload_items)
            resp = client.get(cfg.login.url, params=query_params)
        else:
            raise typer.BadParameter(f"Metodo login {method} non supportato per {cfg.name}.")
        if resp.status_code >= 400:
            raise typer.BadParameter(
                f"Login fallito per {cfg.name}: HTTP {resp.status_code}"
            )
    return DealerSession(client, cfg.login)


@app.command("dealer-sync")
def dealer_sync(
    dealer: str = typer.Argument(..., help="Dealer key o nome (es. ciclodiffusione)"),
    mode: str = typer.Option(
        "all", help="Modalità: policy, catalogo o all", case_sensitive=False
    ),
    max_pages: int = typer.Option(
        3, min=1, help="Max pagine da seguire per seed (solo web)"
    ),
    delay: float = typer.Option(
        0.5, min=0.0, help="Delay (secondi) tra richieste web (solo web)"
    ),
) -> None:
    """Sincronizza un dealer usando providers/dealers.yaml (policy + catalogo).

    - Legge configurazione dealer (mapping, URL policy, seeds).
    - Se mode include 'policy', estrae/aggiorna DealerPolicy.
    - Se mode include 'catalogo', esegue ingest del catalogo (per ora solo web).
    """
    mode_l = mode.strip().lower()
    cfg = find_dealer(dealer)
    if cfg is None:
        raise typer.BadParameter(f"Dealer '{dealer}' non trovato in providers/dealers.yaml")

    rich.print(f"[bold]Dealer[/bold]: {cfg.name} (tipo={cfg.type}, platform={cfg.platform})")

    session = _build_dealer_session(cfg)
    try:
        # Policy
        if mode_l in ("all", "policy") and cfg.policy_url:
            rich.print(f"[cyan]Scarico policy da[/cyan] {cfg.policy_url}")
            r = session.client.get(cfg.policy_url)
            r.raise_for_status()
            ext = parse_policy_html(r.text)
            create_all()
            with SessionLocal() as db:
                row = (
                    db.query(DealerPolicy)
                    .filter(DealerPolicy.dealer == cfg.name)
                    .first()
                )
                if row is None:
                    db.add(
                        DealerPolicy(
                            dealer=cfg.name,
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
            rich.print(
                {
                    "dealer": cfg.name,
                    "base_cost": ext.base_cost,
                    "free_threshold": ext.free_threshold,
                    "lead_days_std": ext.lead_days_std,
                    "confidence": ext.confidence,
                }
            )

        # Catalog ingest (solo web v1)
        if mode_l in ("all", "catalogo"):
            if cfg.type != "web":
                rich.print(
                    f"[yellow]Tipo '{cfg.type}' non ancora supportato per ingest automatico[/yellow]"
                )
            elif not cfg.mapping:
                rich.print(
                    "[yellow]Nessun mapping configurato per questo dealer (campo 'mapping' mancante).[/yellow]"
                )
            else:
                from .adapters.web_adapter import fetch_and_parse_urls, parse_sitemap_urls
                from .dealers import _repo_root

                # Resolve mapping path relative to repository root
                mapping_path = _repo_root() / cfg.mapping

                urls: list[str] = []
                urls.extend(cfg.seeds.urls)
                if cfg.seeds.sitemap:
                    rich.print(f"[cyan]Leggo sitemap[/cyan] {cfg.seeds.sitemap}")
                    more = parse_sitemap_urls(
                        cfg.seeds.sitemap, headers=None, limit=None, session=session.client
                    )
                    urls.extend(more)

                if not urls:
                    rich.print(
                        "[yellow]Nessun URL seed configurato per il dealer; salta ingest catalogo.[/yellow]"
                    )
                else:
                    rich.print(f"[cyan]Ingest catalogo[/cyan] da {len(urls)} seed")
                    products, offers = fetch_and_parse_urls(
                        urls=urls,
                        mapping_yaml=mapping_path,
                        follow_next=True,
                        max_pages=max_pages,
                        delay_sec=delay,
                        headers=None,
                        session=session.client,
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
    finally:
        session.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
