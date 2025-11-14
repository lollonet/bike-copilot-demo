from __future__ import annotations

import os
from pathlib import Path
import importlib

import pytest


def _prepare_env(tmp_db: str) -> None:
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_db}"
    # Reload config/models/ingest_pdf to bind to the fresh DB URL.
    import app.config as app_config
    import app.models as app_models
    import app.ingest_pdf as app_ingest_pdf

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_ingest_pdf)


def test_ingest_pdf_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Smoke test: ingest_pdf.main wires stage_file, extract_from_pdf and upsert."""
    _prepare_env("test_ingest_pdf.db")

    import app.ingest_pdf as ingest_pdf

    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy content")
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text("", encoding="utf-8")

    # Fake extract_from_pdf to avoid real PDF parsing.
    from app.types import ProductInput, OfferInput
    from app.ingest import IngestStats

    def fake_extract(pdf: Path, mapping: Path | None):
        assert pdf == pdf_path
        assert mapping == mapping_path
        products = [
            ProductInput(
                brand="Shimano",
                mpn="CN-HG601",
                ean=None,
                name="Catena 11v",
                category=None,
                speed=None,
                brake=None,
                axle=None,
                rotor=None,
                freehub=None,
            )
        ]
        offers = [
            OfferInput(
                brand="Shimano",
                mpn="CN-HG601",
                supplier="DealerPDF",
                price=24.9,
                in_stock=True,
                lead_time_days=2,
                currency="EUR",
                extra={},
            )
        ]
        return products, offers

    def fake_upsert(products, offers):
        # Basic contract: return an IngestStats instance.
        return IngestStats(
            products_new=len(products),
            products_updated=0,
            offers_upserted=len(offers),
            offers_skipped=0,
        )

    monkeypatch.setattr(ingest_pdf, "extract_from_pdf", fake_extract)
    monkeypatch.setattr(ingest_pdf, "upsert", fake_upsert)

    # Simula argv per argparse.
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingest_pdf",
            "--pdf",
            str(pdf_path),
            "--mapping",
            str(mapping_path),
            "--provider",
            "DemoPDF",
        ],
    )

    from app.ingest_pdf import main

    main()
    out = capsys.readouterr().out
    # Output should contain the IngestStats representation.
    assert "IngestStats" in out
    assert "products_new=1" in out
    assert "offers_upserted=1" in out

