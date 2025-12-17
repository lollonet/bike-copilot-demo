from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import jinja2
import pdfkit
from shutil import which

from .config import settings
from .logging_utils import log_event


def _ensure_out_dir() -> Path:
    out = Path(settings.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def render_quote(context: dict[str, Any]) -> tuple[str, str | None]:
    out_dir = _ensure_out_dir()
    html_path, pdf_path = _quote_paths(out_dir)
    html = _render_quote_html(context)
    html_path.write_text(html, encoding="utf-8")
    pdf_result = _maybe_render_pdf(html_path, pdf_path)
    return str(html_path), pdf_result


def _quote_paths(out_dir: Path) -> tuple[Path, Path]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = f"QUOTE-{ts}"
    html_path = out_dir / f"{base}.html"
    pdf_path = out_dir / f"{base}.pdf"
    return html_path, pdf_path


def _render_quote_html(context: dict[str, Any]) -> str:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("app/templates"))
    tmpl = env.get_template("quote.html")
    # Inject env-level defaults like VAT into the template context
    full_context: dict[str, Any] = {
        **context,
        "env_vat": float(os.environ.get("APP_VAT", "0")),
        "shop_name": os.environ.get("APP_SHOP_NAME", ""),
        "shop_address": os.environ.get("APP_SHOP_ADDRESS", ""),
        "shop_contact": os.environ.get("APP_SHOP_CONTACT", ""),
        "shop_logo": os.environ.get("APP_SHOP_LOGO", ""),
    }
    return tmpl.render(**full_context)


def _maybe_render_pdf(html_path: Path, pdf_path: Path) -> str | None:
    wkhtml = which("wkhtmltopdf")
    if not wkhtml:
        return None
    try:
        _render_pdf_with_wkhtmltopdf(html_path, pdf_path, wkhtml)
        return str(pdf_path)
    except Exception as exc:
        _log_pdf_failure(exc)
        return None


def _render_pdf_with_wkhtmltopdf(
    html_path: Path,
    pdf_path: Path,
    wkhtml: str,
) -> None:
    cfg = pdfkit.configuration(wkhtmltopdf=wkhtml)
    pdfkit.from_file(str(html_path), str(pdf_path), configuration=cfg)


def _log_pdf_failure(exc: Exception) -> None:
    log_event(
        "ERROR",
        op="quote",
        kind="pdf",
        message="wkhtmltopdf failed; falling back to HTML only",
        trace_id=None,
        extra={"error": str(exc)},
    )
