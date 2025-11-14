from __future__ import annotations

from pathlib import Path
from typing import Any, List

import pdfplumber  # type: ignore[import]

from app.adapters import pdf_adapter
from app.adapters.pdf_adapter import extract_from_pdf


class _DummyPage:
    def __init__(self, tables: List[list[list[Any]]]):
        self._tables = tables

    def extract_tables(self) -> List[list[list[Any]]]:
        return self._tables


class _DummyPDF:
    def __init__(self, pages: List[_DummyPage]):
        self.pages = pages

    def __enter__(self) -> "_DummyPDF":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_extract_from_pdf_with_mapping(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% dummy content\n")

    def fake_open(_: str) -> _DummyPDF:
        tables = [
            [
                ["Brand", "MPN", "Name", "Price", "Stock", "Lead"],
                ["Shimano", "CN-HG601", "Catena 11v", "24,90", "X", "2"],
            ]
        ]
        return _DummyPDF([_DummyPage(tables)])

    monkeypatch.setattr(pdf_adapter, "pdfplumber", pdfplumber)
    monkeypatch.setattr(pdf_adapter.pdfplumber, "open", fake_open)

    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        "\n".join(
            [
                "supplier: PDFShop",
                "brand_col: Brand",
                "mpn_col: MPN",
                "name_col: Name",
                "price_col: Price",
                "stock_col: Stock",
                "lead_col: Lead",
            ]
        ),
        encoding="utf-8",
    )

    products, offers = extract_from_pdf(pdf_path, mapping)
    assert len(products) == 1
    assert len(offers) == 1
    p = products[0]
    o = offers[0]
    assert p.brand == "Shimano"
    assert p.mpn == "CN-HG601"
    assert o.supplier == "PDFShop"
    assert abs(o.price - 24.90) < 0.01
    assert o.in_stock is True
    assert o.lead_time_days == 2

