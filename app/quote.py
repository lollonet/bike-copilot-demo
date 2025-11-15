from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
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
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = f"QUOTE-{ts}"
    html_path = out_dir / f"{base}.html"
    pdf_path = out_dir / f"{base}.pdf"

    # Render HTML
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("app/templates"))
    tmpl = env.get_template("quote.html")
    # Inject env-level defaults like VAT into the template context
    html = tmpl.render(
        **{
            **context,
            "env_vat": float(os.environ.get("APP_VAT", "0")),
            "shop_name": os.environ.get("APP_SHOP_NAME", ""),
            "shop_address": os.environ.get("APP_SHOP_ADDRESS", ""),
            "shop_contact": os.environ.get("APP_SHOP_CONTACT", ""),
            "shop_logo": os.environ.get("APP_SHOP_LOGO", ""),
        }
    )
    html_path.write_text(html, encoding="utf-8")

    # Try PDF if wkhtmltopdf is available
    wkhtml = which("wkhtmltopdf")
    if wkhtml:
        try:
            cfg = pdfkit.configuration(wkhtmltopdf=wkhtml)
            pdfkit.from_file(str(html_path), str(pdf_path), configuration=cfg)
            return str(html_path), str(pdf_path)
        except Exception as exc:
            log_event(
                "ERROR",
                op="quote",
                kind="pdf",
                message="wkhtmltopdf failed; falling back to HTML only",
                trace_id=None,
                extra={"error": str(exc)},
            )
            return str(html_path), None
    else:
        return str(html_path), None
