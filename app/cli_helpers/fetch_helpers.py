"""Helper functions for fetch CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Any

from ..adapters.web_adapter import fetch_and_parse_urls, parse_sitemap_urls
from ..ingest import IngestStats, upsert
from ..logging_utils import log_exception
from ..models import DealerPolicy
from ..types import OfferInput, ProductInput
from ..policy import PolicyExtract

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    import httpx


def build_headers_from_cli(header: list[str] | None) -> dict[str, str]:
    """Parse header options from CLI format to dict.

    Args:
        header: List of "key:value" strings from CLI options

    Returns:
        Dictionary of HTTP headers
    """
    hdrs: dict[str, str] = {}
    for h in header or []:
        if ":" in h:
            k, v = h.split(":", 1)
            hdrs[k.strip()] = v.strip()
    return hdrs


def upsert_dealer_policy(
    db: Session,
    dealer: str,
    ext: PolicyExtract,
) -> None:
    """Upsert dealer policy extracted from HTML.

    Args:
        db: Database session
        dealer: Dealer name
        ext: Extracted policy data with base_cost, free_threshold, etc.
    """
    from sqlalchemy import select

    row = db.scalar(select(DealerPolicy).where(DealerPolicy.dealer == dealer))
    if row is None:
        db.add(
            DealerPolicy(
                dealer=dealer,
                base_cost=ext.base_cost,
                free_threshold=ext.free_threshold,
                lead_days_std=ext.lead_days_std,
                source="rules",
                confidence=ext.confidence,
            )
        )
    else:
        row.base_cost = ext.base_cost
        row.free_threshold = ext.free_threshold
        row.lead_days_std = ext.lead_days_std
        row.source = "rules"
        row.confidence = ext.confidence
    db.commit()


def fetch_and_ingest_web(
    urls: list[str],
    mapping: Path,
    follow_next: bool,
    max_pages: int,
    delay: float,
    headers: dict[str, str],
) -> IngestStats:
    """Fetch URLs, parse with mapping, and ingest to database.

    Args:
        urls: List of URLs to fetch
        mapping: Path to mapping YAML file
        follow_next: Whether to follow pagination links
        max_pages: Maximum pages to fetch per seed URL
        delay: Delay in seconds between requests
        headers: HTTP headers to include

    Returns:
        IngestStats with counts of products/offers upserted
    """
    products, offers = fetch_and_parse_urls(
        urls=urls,
        mapping_yaml=mapping,
        follow_next=follow_next,
        max_pages=max_pages,
        delay_sec=delay,
        headers=headers,
    )
    return upsert(products, offers)


def sitemap_target_urls(
    sitemap: str,
    headers: dict[str, str],
    contains: str,
    limit: int,
) -> list[str]:
    """Extract URLs from sitemap that match filter criteria.

    Args:
        sitemap: Sitemap or sitemap index URL
        headers: HTTP headers
        contains: Only include URLs containing this substring
        limit: Maximum URLs to return (0 = no limit)

    Returns:
        List of filtered URLs from sitemap
    """
    urls = parse_sitemap_urls(sitemap, headers=headers, limit=(limit or None))
    return [u for u in urls if contains in u]


def fetch_sitemap_details(
    urls: list[str],
    mapping: Path,
    headers: dict[str, str],
    delay: float,
) -> tuple[list[ProductInput], list[OfferInput], int]:
    """Fetch and parse product detail pages from sitemap URLs.

    Args:
        urls: List of product detail page URLs
        mapping: Path to mapping YAML file
        headers: HTTP headers
        delay: Delay in seconds between requests

    Returns:
        Tuple of (products, offers, failures) where failures is the count of failed fetches
    """
    from time import sleep

    from ..adapters.web_adapter import _load_mapping  # type: ignore
    import httpx

    mapping_obj = _load_mapping(mapping)
    products: list[ProductInput] = []
    offers: list[OfferInput] = []
    seen: set[tuple[str, str, str]] = set()
    failures = 0
    with httpx.Client(
        timeout=10.0,
        headers=headers or {"User-Agent": "BikeCopilotBot/0.1"},
        follow_redirects=True,
        verify=True,
    ) as client:
        for u in urls:
            success = fetch_single_sitemap_url(
                client, u, mapping_obj, seen, products, offers, delay, sleep
            )
            if not success:
                failures += 1
    return products, offers, failures


def fetch_single_sitemap_url(
    client: httpx.Client,
    url: str,
    mapping_obj: Any,
    seen: set[tuple[str, str, str]],
    products: list[ProductInput],
    offers: list[OfferInput],
    delay: float,
    sleep: Callable[[float], None],
) -> bool:
    """Fetch and parse a single sitemap URL, avoiding duplicates.

    Args:
        client: httpx.Client instance
        url: URL to fetch
        mapping_obj: Loaded mapping configuration
        seen: Set of (brand, mpn, supplier) tuples already processed
        products: List to append products to
        offers: List to append offers to
        delay: Delay in seconds after request
        sleep: Sleep function

    Returns:
        True if successful, False if failed
    """
    try:
        r = client.get(url)
        r.raise_for_status()
        from ..adapters.web_adapter import parse_detail_html  # type: ignore

        p, o = parse_detail_html(r.text, mapping_obj)
        if p and o:
            key = (p.brand, p.mpn, o.supplier)
            if key in seen:
                return True  # Duplicate, but not an error
            seen.add(key)
            products.append(p)
            offers.append(o)
        return True
    except Exception as exc:
        log_exception(
            "cli", "web-ingest", "failed to fetch sitemap url", exc, extra={"url": url}
        )
        return False
    finally:
        sleep(max(0.0, delay))
