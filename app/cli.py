from __future__ import annotations

from pathlib import Path

import rich
import typer
from rich.table import Table

from .adapters.csv_adapter import parse_offers_csv, parse_products_csv
from .adapters.pdf_adapter import extract_from_pdf
from .adapters.web_adapter import parse_file as parse_web_file
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
    customer_name: str = typer.Option(...),
    customer_contact: str = typer.Option(...),
    validity_days: int = typer.Option(7),
    notes: str | None = typer.Option(None),
) -> None:
    """Render a quote for an existing offer and print artifact paths."""
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
            "item": {
                "brand": product.brand,
                "mpn": product.mpn,
                "name": product.name,
                "supplier": offer.supplier,
                "price": offer.price,
                "in_stock": offer.in_stock,
                "lead_time_days": offer.lead_time_days,
            },
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
