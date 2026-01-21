"""Service-related CLI commands for health checks and server processes."""

from __future__ import annotations

from pathlib import Path

import rich
import typer

from ..cli_helpers.service_helpers import (
    build_dealer_session,
    print_dealer_intro,
    require_dealer_cfg,
    sync_dealer_catalog_if_needed,
    sync_dealer_policy_if_needed,
)
from ..logging_utils import log_exception

app = typer.Typer(help="Service commands")


@app.command()
def health() -> None:
    """Check system health and dependencies."""
    try:
        from shutil import which

        from .. import __version__

        info = {
            "status": "ok",
            "db": True,
            "pdfkit": bool(which("wkhtmltopdf")),
            "version": __version__,
        }
        rich.print(info)
    except Exception as exc:
        log_exception("cli", "health", "health check failed", exc)
        raise typer.Exit(code=1)


@app.command()
def ui(port: int = typer.Option(7860), host: str = typer.Option("0.0.0.0")) -> None:
    """Launch Gradio UI interface.

    Note: Delegates to bin/run_ui.py to avoid architectural boundary violation.
    CLI layer should not import UI layer.
    """
    try:
        import subprocess
        import sys

        # Find project root (where bin/ directory is located)
        cli_file = Path(__file__).resolve()
        project_root = cli_file.parent.parent.parent
        ui_script = project_root / "bin" / "run_ui.py"

        # Call the UI entry script with the same arguments
        result = subprocess.run(
            [sys.executable, str(ui_script), "--port", str(port), "--host", host],
            check=False,
        )
        sys.exit(result.returncode)
    except Exception as exc:
        log_exception(
            "cli", "ui", "failed to launch UI", exc, extra={"port": port, "host": host}
        )
        raise typer.Exit(code=1)


@app.command()
def api(port: int = typer.Option(8000), host: str = typer.Option("0.0.0.0")) -> None:
    """Launch FastAPI server."""
    try:
        import uvicorn

        uvicorn.run("app.api:app", host=host, port=port, reload=False)
    except Exception as exc:
        log_exception(
            "cli",
            "api",
            "failed to launch API server",
            exc,
            extra={"port": port, "host": host},
        )
        raise typer.Exit(code=1)


@app.command(
    "sync",
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
    """Synchronize dealer policy and catalog."""
    try:
        mode_l = mode.strip().lower()
        cfg = require_dealer_cfg(dealer)
        print_dealer_intro(cfg)

        from ..dealers import _repo_root

        mapping_path = _repo_root() / cfg.mapping if cfg.mapping else None

        session = build_dealer_session(cfg)
        try:
            sync_dealer_policy_if_needed(cfg, mode_l, session)
            sync_dealer_catalog_if_needed(
                cfg, mode_l, session, max_pages, delay, mapping_path
            )
        finally:
            session.close()
    except Exception as exc:
        log_exception(
            "cli",
            "dealer-sync",
            "failed to sync dealer",
            exc,
            extra={"dealer": dealer, "mode": mode},
        )
        raise typer.Exit(code=1)


# For backwards compatibility, register commands with original names when imported directly
def register_to_main_app(main_app: typer.Typer) -> None:
    """Register service commands to main CLI app.

    Args:
        main_app: Main Typer application to register commands to
    """
    main_app.command("health")(health)
    main_app.command("ui")(ui)
    main_app.command("api")(api)
    main_app.command("dealer-sync")(dealer_sync)
