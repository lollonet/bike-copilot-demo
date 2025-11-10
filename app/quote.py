from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import jinja2
import pdfkit
from shutil import which

from .config import settings


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
    html = tmpl.render(**context)
    html_path.write_text(html, encoding="utf-8")

    # Try PDF if wkhtmltopdf is available
    wkhtml = which("wkhtmltopdf")
    if wkhtml:
        try:
            cfg = pdfkit.configuration(wkhtmltopdf=wkhtml)
            pdfkit.from_file(str(html_path), str(pdf_path), configuration=cfg)
            return str(html_path), str(pdf_path)
        except Exception:
            # Fallback to HTML only
            return str(html_path), None
    else:
        return str(html_path), None

