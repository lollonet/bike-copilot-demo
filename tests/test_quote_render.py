from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.quote import render_quote


def test_render_quote_creates_html_only_when_wkhtmltopdf_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "out"
    monkeypatch.setenv("APP_OUT_DIR", str(out_dir))
    # Force wkhtmltopdf to be considered missing
    monkeypatch.setenv("PATH", "")

    context: dict[str, Any] = {
        "customer_name": "Test",
        "customer_contact": "contact@example.com",
        "items": [],
        "totals": {"subtotal": 0.0, "shipping": 0.0, "total": 0.0},
    }

    html_path_str, pdf_path_str = render_quote(context)
    html_path = Path(html_path_str)

    assert html_path.exists()
    assert pdf_path_str is None or not Path(pdf_path_str).exists()
