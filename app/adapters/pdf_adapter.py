from __future__ import annotations

from pathlib import Path

from ..types import OfferInput, ProductInput


def extract_from_pdf(_path: Path) -> tuple[list[ProductInput], list[OfferInput]]:
    # Placeholder. Implement with a PDF table extractor (e.g., pdfplumber)
    # and a per-provider mapping. Keep raw→parsed→normalized pipeline.
    raise NotImplementedError("PDF adapter not implemented yet")

