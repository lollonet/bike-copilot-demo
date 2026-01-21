from __future__ import annotations

import os
from pathlib import Path

import rich
import typer
from dotenv import load_dotenv
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import Session

from .logging_utils import log_exception

from .adapters.web_adapter import (
    fetch_and_parse_urls,
    build_search_urls,
)
from .ingest import IngestStats, upsert
from .models import (
    EventLog,
    SessionLocal,
    SupplierOffer,
    Product,
    create_all,
)
from .quote import render_quote
from .search import search
from .types import Brake, Freehub, QuoteResponse, Rotor, SearchRequest
from .commands import data_commands, fetch_commands, ingest_commands, service_commands


app = typer.Typer(add_completion=True, no_args_is_help=True, help="Bike Copilot CLI")
load_dotenv()

# Register fetch commands
fetch_commands.register_to_main_app(app)

# Register ingest commands
ingest_commands.register_to_main_app(app)

# Register data commands
data_commands.register_to_main_app(app)

# Register service commands
service_commands.register_to_main_app(app)


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
            except OSError as exc:
                log_exception(
                    "cli",
                    "reset-db",
                    "failed to remove sqlite file",
                    exc,
                    extra={"path": p},
                )
    # Recreate
    create_all()
    rich.print({"db": "reset", "url": url})


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
