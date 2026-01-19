"""Ingest-related CLI commands for processing and importing data."""

from __future__ import annotations

import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import rich
import typer

from ..adapters.csv_adapter import parse_offers_csv, parse_products_csv
from ..adapters.csv_mapped_adapter import parse_unified_csv
from ..adapters.pdf_adapter import extract_from_pdf
from ..cli_helpers.ingest_helpers import (
    ProviderStatus,
    compute_synth_summary,
    generate_synthetic_offers,
    group_offers_by_product,
    provider_lock,
    release_lock,
    run_ciclodiffusione,
    run_dealer_from_yaml,
    run_montanini,
    status_reporter,
    upsert_synthetic_offers,
)
from ..dealers import find_dealer
from ..ingest import IngestStats, upsert
from ..logging_utils import log_exception
from ..models import create_all

app = typer.Typer(help="Ingest commands")


@app.command("csv")
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
    try:
        ps = parse_products_csv(products)
        os_list = parse_offers_csv(offers)
        stats: IngestStats = upsert(ps, os_list)
        rich.print(stats)
    except Exception as exc:
        log_exception(
            "cli",
            "ingest-csv",
            "failed to ingest CSV files",
            exc,
            extra={"products": str(products), "offers": str(offers)},
        )
        raise typer.Exit(code=1)


@app.command("pdf")
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
    try:
        products, offers = extract_from_pdf(pdf, mapping)
        stats: IngestStats = upsert(products, offers)
        rich.print(stats)
    except Exception as exc:
        log_exception(
            "cli",
            "ingest-pdf",
            "failed to extract and ingest PDF",
            exc,
            extra={"pdf": str(pdf), "mapping": str(mapping) if mapping else None},
        )
        raise typer.Exit(code=1)


@app.command("csv-mapped")
def ingest_csv_mapped(
    csv: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
) -> None:
    """Ingest a single CSV using a mapping YAML to canonical fields."""
    try:
        products, offers = parse_unified_csv(csv, mapping)
        stats: IngestStats = upsert(products, offers)
        rich.print(stats)
    except Exception as exc:
        log_exception(
            "cli",
            "ingest-csv-mapped",
            "failed to ingest mapped CSV",
            exc,
            extra={"csv": str(csv), "mapping": str(mapping)},
        )
        raise typer.Exit(code=1)


@app.command("all-parallel")
def ingest_all_parallel(
    queries: str = typer.Option(
        "copertone sella casco catena",
        "--queries",
        "-q",
        help="Space-separated search queries for Ciclodiffusione",
    ),
    max_pages: int = typer.Option(
        5, help="Max pages to follow for search-based crawlers"
    ),
    delay: float = typer.Option(0.8, help="Delay between requests (seconds)"),
    seed_csv: Path = typer.Option(
        Path("catalogo_real_mtb.csv"), help="CSV to seed before crawls"
    ),
    seed_mapping: Path = typer.Option(
        Path("providers/csv-catalogo-mtb.yaml"), help="Mapping for seed CSV"
    ),
    progress_interval: int = typer.Option(60, help="Status report interval (seconds)"),
    lock_dir: Path = typer.Option(
        Path("/tmp/bike-copilot-locks"), help="Directory for provider locks"
    ),
) -> None:
    """Seed CSV then crawl all providers in parallel with per-minute status."""
    try:
        # Import DealerSession here to avoid circular imports
        from ..cli import DealerSession, _build_dealer_session

        create_all()
        products, offers = parse_unified_csv(seed_csv, seed_mapping)
        seed_stats = upsert(products, offers)
        rich.print({"seed": seed_stats})

        statuses: dict[str, ProviderStatus] = {}
        lock = threading.Lock()
        stop_event = threading.Event()

        def _launch(
            name: str, supplier: str, fn: Callable[[], IngestStats | None]
        ) -> Callable[[], IngestStats | None]:
            status: ProviderStatus = {
                "name": name,
                "supplier": supplier,
                "state": "pending",
                "pages_done": 0,
                "products": 0,
                "offers": 0,
                "total_seeds": None,
                "message": "",
                "lock_file": None,
            }
            statuses[name] = status

            def _wrapped() -> IngestStats | None:
                lock_file = provider_lock(name, lock_dir)
                if lock_file is None:
                    status["state"] = "skipped"
                    status["message"] = "another run in progress (lock held)"
                    return None
                status["lock_file"] = str(lock_file)
                status["state"] = "running"
                try:
                    return fn()
                finally:
                    status["state"] = (
                        "done" if status.get("state") != "error" else status["state"]
                    )
                    release_lock(lock_file)

            return _wrapped

        queries_list = [q for q in queries.split(" ") if q.strip()]

        cfgs = {
            key: find_dealer(key)
            for key in ["ciclodiffusione", "rms", "ciclopromo", "bikeparts"]
        }

        def _build_session_for(
            key: str, status: ProviderStatus
        ) -> DealerSession | None:
            cfg = cfgs.get(key)
            if cfg is None:
                status["state"] = "skipped"
                status["message"] = "dealer not found in providers/dealers.yaml"
                return None
            try:
                return _build_dealer_session(cfg)
            except Exception as exc:  # pragma: no cover
                status["state"] = "skipped"
                status["message"] = f"auth/session error: {exc}"
                return None

        tasks: dict[str, Callable[[], IngestStats | None]] = {
            "ciclimontanini": _launch(
                "ciclimontanini",
                "CicliMontanini",
                lambda status=statuses["ciclimontanini"], lk=lock: run_montanini(
                    status, lk
                ),
            ),
            "ciclodiffusione": _launch(
                "ciclodiffusione",
                "Ciclodiffusione",
                lambda cfg_key="ciclodiffusione",
                q=queries_list,
                mp=max_pages,
                d=delay: (
                    run_ciclodiffusione(
                        statuses[cfg_key],
                        lock,
                        cfg,
                        session,
                        q,
                        mp,
                        d,
                    )
                    if (cfg := cfgs.get(cfg_key))
                    and (session := _build_session_for(cfg_key, statuses[cfg_key]))
                    else None
                ),
            ),
            "rms": _launch(
                "rms",
                "RMS",
                lambda cfg_key="rms", mp=max_pages, d=delay: (
                    run_dealer_from_yaml(
                        statuses[cfg_key],
                        lock,
                        cfg,
                        session,
                        d,
                        mp,
                    )
                    if (cfg := cfgs.get(cfg_key))
                    and (session := _build_session_for(cfg_key, statuses[cfg_key]))
                    else None
                ),
            ),
            "ciclopromo": _launch(
                "ciclopromo",
                "CicloPromo",
                lambda cfg_key="ciclopromo", mp=max_pages, d=delay: (
                    run_dealer_from_yaml(
                        statuses[cfg_key],
                        lock,
                        cfg,
                        session,
                        d,
                        mp,
                    )
                    if (cfg := cfgs.get(cfg_key))
                    and (session := _build_session_for(cfg_key, statuses[cfg_key]))
                    else None
                ),
            ),
            "bikeparts": _launch(
                "bikeparts",
                "Bikeparts",
                lambda cfg_key="bikeparts", mp=max_pages, d=delay: (
                    run_dealer_from_yaml(
                        statuses[cfg_key],
                        lock,
                        cfg,
                        session,
                        d,
                        mp,
                    )
                    if (cfg := cfgs.get(cfg_key))
                    and (session := _build_session_for(cfg_key, statuses[cfg_key]))
                    else None
                ),
            ),
        }

        reporter = threading.Thread(
            target=status_reporter,
            args=(stop_event, statuses, progress_interval, lock),
            daemon=True,
        )
        reporter.start()

        results: dict[str, IngestStats | None] = {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            future_map = {pool.submit(fn): name for name, fn in tasks.items()}
            for fut in as_completed(future_map):
                name = future_map[fut]
                try:
                    results[name] = fut.result()
                except Exception as exc:  # pragma: no cover
                    results[name] = None
                    with lock:
                        statuses[name]["state"] = "error"
                        statuses[name]["message"] = str(exc)
                    log_exception("cli", "ingest-all-parallel", f"{name} failed", exc)

        stop_event.set()
        reporter.join(timeout=2)

        rich.print({"results": {k: str(v) for k, v in results.items()}})
    except Exception as exc:
        log_exception(
            "cli",
            "ingest-all-parallel",
            "failed to run parallel ingestion",
            exc,
            extra={"queries": queries},
        )
        raise typer.Exit(code=1)


@app.command("csv-synth")
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
    try:
        base_products, base_offers = parse_unified_csv(csv, mapping)

        stats = upsert(base_products, base_offers)
        rng = random.Random(42)
        grouped = group_offers_by_product(base_offers)
        extra_offers = generate_synthetic_offers(
            grouped, suppliers, coverage, jitter, rng
        )
        stats = upsert_synthetic_offers(extra_offers, stats)
        summary = compute_synth_summary()
        rich.print({**summary, "ingest": stats.__dict__})
    except Exception as exc:
        log_exception(
            "cli",
            "ingest-csv-synth",
            "failed to ingest and synthesize offers",
            exc,
            extra={"csv": str(csv), "mapping": str(mapping)},
        )
        raise typer.Exit(code=1)


# For backwards compatibility, register commands with original names when imported directly
def register_to_main_app(main_app: typer.Typer) -> None:
    """Register ingest commands to main CLI app with original command names.

    Args:
        main_app: Main Typer application to register commands to
    """
    main_app.command("ingest-csv")(ingest_csv)
    main_app.command("ingest-pdf")(ingest_pdf)
    main_app.command("ingest-csv-mapped")(ingest_csv_mapped)
    main_app.command("ingest-all-parallel")(ingest_all_parallel)
    main_app.command("ingest-csv-synth")(ingest_csv_synth)
