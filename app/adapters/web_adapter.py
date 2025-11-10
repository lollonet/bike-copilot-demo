from __future__ import annotations

from ..types import OfferInput, ProductInput


def fetch_from_provider(_provider: str) -> tuple[list[ProductInput], list[OfferInput]]:
    # Placeholder. Implement with httpx + HTML/API parsing, cache, and etiquette.
    raise NotImplementedError("Web adapter not implemented yet")

