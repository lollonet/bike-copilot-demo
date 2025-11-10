from __future__ import annotations

from pathlib import Path

import rich
import typer
from rich.table import Table
import os
import random

from .adapters.csv_adapter import parse_offers_csv, parse_products_csv
from .adapters.pdf_adapter import extract_from_pdf
from .adapters.web_adapter import (
    parse_file as parse_web_file,
    fetch_and_parse_urls,
    build_search_urls,
)
from .adapters.csv_mapped_adapter import parse_unified_csv
from .ingest import IngestStats, upsert
from .models import EventLog, SessionLocal, SupplierOffer, create_all
from .quote import render_quote
from .search import search
from .types import Brake, Freehub, QuoteResponse, Rotor, SearchRequest


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
