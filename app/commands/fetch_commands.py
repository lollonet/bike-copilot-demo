"""Fetch-related CLI commands for retrieving and ingesting data from external sources."""

from __future__ import annotations

from pathlib import Path

import httpx
import rich
import typer

from ..adapters.web_adapter import parse_file as parse_web_file
from ..adapters.playwright_fetcher import fetch_rendered
from ..cli_helpers.fetch_helpers import (
    build_headers_from_cli,
    fetch_and_ingest_web,
    fetch_sitemap_details,
    sitemap_target_urls,
    upsert_dealer_policy,
)
from ..ingest import IngestStats, upsert
from ..logging_utils import log_exception
from ..models import SessionLocal, create_all
from ..policy import parse_policy_html


app = typer.Typer(help="Fetch commands")


@app.command("policy")
def fetch_policy(
    dealer: str = typer.Option(..., help="Dealer name"),
    url: str = typer.Option(..., help="URL pagina Spedizioni/Condizioni"),
    header: list[str] = typer.Option(None, help="extra HTTP headers (key:value)"),
) -> None:
    """Fetch a shipping policy page and upsert DealerPolicy using deterministic rules."""
    try:
        hdrs = build_headers_from_cli(header)
        create_all()
        with httpx.Client(
            timeout=15.0,
            headers=hdrs or {"User-Agent": "BikeCopilotBot/0.1"},
            follow_redirects=True,
            verify=True,
        ) as client:
            r = client.get(url)
            r.raise_for_status()
            ext = parse_policy_html(r.text)
        with SessionLocal() as db:
            upsert_dealer_policy(db, dealer, ext)
        rich.print(
            {
                "dealer": dealer,
                "base_cost": ext.base_cost,
                "free_threshold": ext.free_threshold,
                "lead_days_std": ext.lead_days_std,
                "confidence": ext.confidence,
            }
        )
    except Exception as exc:
        log_exception(
            "cli",
            "fetch-policy",
            "failed to fetch dealer policy",
            exc,
            extra={"dealer": dealer, "url": url},
        )
        raise typer.Exit(code=1)


@app.command("web")
def fetch_web(
    html: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
    mapping: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True
    ),
) -> None:
    """Parse a local HTML file with a mapping YAML and upsert results."""
    try:
        products, offers = parse_web_file(html, mapping)
        stats: IngestStats = upsert(products, offers)
        rich.print(stats)
    except Exception as exc:
        log_exception(
            "cli",
            "fetch-web",
            "failed to parse HTML file",
            exc,
            extra={"html": str(html), "mapping": str(mapping)},
        )
        raise typer.Exit(code=1)


@app.command("web-url")
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
    try:
        hdrs = build_headers_from_cli(header)
        stats = fetch_and_ingest_web(url, mapping, follow_next, max_pages, delay, hdrs)
        rich.print(stats)
    except Exception as exc:
        log_exception(
            "cli",
            "fetch-web-url",
            "failed to fetch remote pages",
            exc,
            extra={"urls": url, "mapping": str(mapping)},
        )
        raise typer.Exit(code=1)


@app.command("sitemap")
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
    try:
        hdrs = build_headers_from_cli(header)
        urls = sitemap_target_urls(sitemap, hdrs, contains, limit)
        products, offers, failures = fetch_sitemap_details(urls, mapping, hdrs, delay)
        stats: IngestStats = upsert(products, offers)
        rich.print({"visited": len(urls), "failures": failures, **stats.__dict__})
    except Exception as exc:
        log_exception(
            "cli",
            "fetch-sitemap",
            "failed to fetch sitemap",
            exc,
            extra={"sitemap": sitemap, "mapping": str(mapping)},
        )
        raise typer.Exit(code=1)


@app.command("rendered")
def fetch_rendered_cmd(
    url: str = typer.Argument(..., help="URL to fetch with Playwright Chromium"),
    wait_ms: int = typer.Option(1500, help="Wait after load (ms)"),
    login_url: str | None = typer.Option(None, help="Login page URL (optional)"),
    username: str | None = typer.Option(None, help="Login username"),
    password: str | None = typer.Option(None, help="Login password"),
    user_selector: str = typer.Option("#username", help="CSS selector for username"),
    pass_selector: str = typer.Option("#password", help="CSS selector for password"),
    submit_selector: str = typer.Option(
        "button[type=submit]", help="Submit button selector"
    ),
) -> None:
    """Fetch a JS-heavy page; optional simple form login."""
    try:
        html = fetch_rendered(
            url,
            wait_ms=wait_ms,
            login_url=login_url,
            username=username,
            password=password,
            user_selector=user_selector,
            pass_selector=pass_selector,
            submit_selector=submit_selector,
        )
        rich.print(html)
    except Exception as exc:
        log_exception(
            "cli",
            "fetch-rendered",
            "failed to fetch rendered page",
            exc,
            extra={"url": url},
        )
        raise typer.Exit(code=1)


# For backwards compatibility, register commands with original names when imported directly
def register_to_main_app(main_app: typer.Typer) -> None:
    """Register fetch commands to main CLI app with original command names.

    Args:
        main_app: Main Typer application to register commands to
    """
    main_app.command("fetch-policy")(fetch_policy)
    main_app.command("fetch-web")(fetch_web)
    main_app.command("fetch-web-url")(fetch_web_url)
    main_app.command("fetch-sitemap")(fetch_sitemap)
    main_app.command("fetch-rendered")(fetch_rendered_cmd)
