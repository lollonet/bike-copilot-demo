"""Data-related CLI commands for export and import operations."""

from __future__ import annotations

from pathlib import Path

import rich
import typer
import yaml

from ..cli_helpers.data_helpers import (
    apply_pn_alias_blocks,
    build_export_rows,
    build_norm_mpn_index,
    query_export_rows,
    render_export_table,
)
from ..logging_utils import log_exception
from ..models import SessionLocal, create_all

app = typer.Typer(help="Data commands")


@app.command("md")
def dump_md(
    limit: int | None = typer.Option(None, help="Max rows; omit for all"),
    supplier: str | None = typer.Option(None, help="Filter by supplier"),
    brand: str | None = typer.Option(None, help="Filter by brand"),
    category: str | None = typer.Option(None, help="Filter by category"),
) -> None:
    """Dump joined product+offer rows as a Markdown table for inspection."""
    try:
        rows = query_export_rows(limit, supplier, brand, category)
        items = build_export_rows(rows)
        table = render_export_table(items)
        print(table)
    except Exception as exc:
        log_exception(
            "cli",
            "dump-md",
            "failed to export data",
            exc,
            extra={
                "limit": limit,
                "supplier": supplier,
                "brand": brand,
                "category": category,
            },
        )
        raise typer.Exit(code=1)


@app.command("alias-import")
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
    try:
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or []
        if not isinstance(data, list):
            raise typer.BadParameter("YAML root must be a list of dealer blocks")
        create_all()
        with SessionLocal() as db:
            norm_to_product = build_norm_mpn_index(db)
            inserted, updated = apply_pn_alias_blocks(db, data, norm_to_product)
        rich.print(
            f"[green]Alias PN importati da {yaml_file} — inseriti: {inserted}, aggiornati: {updated}[/green]"
        )
    except Exception as exc:
        log_exception(
            "cli",
            "pn-alias-import",
            "failed to import PN aliases",
            exc,
            extra={"yaml_file": str(yaml_file)},
        )
        raise typer.Exit(code=1)


# For backwards compatibility, register commands with original names when imported directly
def register_to_main_app(main_app: typer.Typer) -> None:
    """Register data commands to main CLI app with original command names.

    Args:
        main_app: Main Typer application to register commands to
    """
    main_app.command("dump-md")(dump_md)
    main_app.command("pn-alias-import")(pn_alias_import)
