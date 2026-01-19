"""Helper functions for ingest CLI commands."""

from __future__ import annotations

import json
import os
import random
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable, TypedDict

import yaml
from sqlalchemy import func, select

from ..adapters.web_adapter import (
    build_search_urls,
    fetch_and_parse_urls,
    parse_sitemap_urls,
)
from ..ingest import IngestStats, upsert
from ..models import SessionLocal, SupplierOffer
from ..types import OfferInput

if TYPE_CHECKING:
    from typing import Any

    from ..dealers import DealerConfig

    # DealerSession is still in cli.py, will be extracted in Phase 4
    # Using Any to avoid circular import
    DealerSession = Any


# --- Parallel ingest orchestrator types and helpers ---


class ProviderStatus(TypedDict, total=False):
    """Status information for a provider during parallel ingestion."""

    name: str
    supplier: str
    state: str
    pages_done: int
    products: int
    offers: int
    total_seeds: int | None
    message: str
    lock_file: str | None


def provider_lock(name: str, lock_dir: Path) -> Path | None:
    """Create a per-provider lock file; return None if already locked.

    Args:
        name: Provider name
        lock_dir: Directory to store lock files

    Returns:
        Path to lock file if created, None if already locked
    """
    lock_dir.mkdir(parents=True, exist_ok=True)
    lf = lock_dir / f"{name}.lock"
    try:
        fd = os.open(lf, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        lf.write_text(str(os.getpid()))
        return lf
    except FileExistsError:
        return None


def release_lock(lock_file: Path | None) -> None:
    """Release a provider lock file.

    Args:
        lock_file: Path to lock file to release
    """
    if lock_file and lock_file.exists():
        try:
            lock_file.unlink()
        except OSError:
            pass


def load_dealer_seeds(key: str) -> list[str]:
    """Load seed URLs for a dealer from providers/dealers.yaml.

    Args:
        key: Dealer key in dealers.yaml

    Returns:
        List of seed URLs
    """
    data = (
        yaml.safe_load(Path("providers/dealers.yaml").read_text(encoding="utf-8")) or {}
    )
    for d in data.get("dealers", []):
        if d.get("key") == key:
            return d.get("seeds", {}).get("urls", []) or []
    return []


def default_progress_cb(
    status: ProviderStatus, lock: threading.Lock
) -> Callable[[str, int, int, int], None]:
    """Create a progress callback that updates provider status.

    Args:
        status: Provider status dict to update
        lock: Threading lock for safe updates

    Returns:
        Progress callback function
    """

    def _cb(url: str, page_idx: int, products: int, offers: int) -> None:  # noqa: ARG001
        with lock:
            status["pages_done"] = status.get("pages_done", 0) + 1
            status["products"] = products
            status["offers"] = offers

    return _cb


def run_montanini(status: ProviderStatus, lock: threading.Lock) -> IngestStats:
    """Fetch and ingest products from CicliMontanini sitemaps.

    Args:
        status: Provider status dict to update
        lock: Threading lock for safe updates

    Returns:
        Ingestion statistics
    """
    urls = parse_sitemap_urls(
        "https://www.ciclimontanini.com/product-sitemap.xml",
        headers=None,
        limit=None,
    ) + parse_sitemap_urls(
        "https://www.ciclimontanini.com/product-sitemap2.xml",
        headers=None,
        limit=None,
    )
    status["total_seeds"] = len(urls)
    products, offers = fetch_and_parse_urls(
        urls,
        Path("providers/web-ciclimontanini.yaml"),
        follow_next=False,
        max_pages=1,
        delay_sec=0.75,
        progress_cb=default_progress_cb(status, lock),
    )
    return upsert(products, offers)


def run_ciclodiffusione(
    status: ProviderStatus,
    lock: threading.Lock,
    cfg: DealerConfig,
    session: DealerSession,
    queries: list[str],
    max_pages: int,
    delay: float,
) -> IngestStats:
    """Fetch and ingest products from Ciclodiffusione.

    Args:
        status: Provider status dict to update
        lock: Threading lock for safe updates
        cfg: Dealer configuration
        session: Authenticated dealer session
        queries: Search queries to run
        max_pages: Maximum pages to follow
        delay: Delay between requests in seconds

    Returns:
        Ingestion statistics
    """
    mapping = Path(cfg.mapping or "providers/web-ciclodiffusione.yaml")
    seeds: list[str] = list(cfg.seeds.urls)
    if not seeds:
        for q in queries:
            seeds.extend(build_search_urls(q, mapping))
    status["total_seeds"] = len(seeds)
    products, offers = fetch_and_parse_urls(
        seeds,
        mapping,
        follow_next=True,
        max_pages=max_pages,
        delay_sec=delay,
        progress_cb=default_progress_cb(status, lock),
        session=session.client,
    )
    return upsert(products, offers)


def run_dealer_from_yaml(
    status: ProviderStatus,
    lock: threading.Lock,
    cfg: DealerConfig,
    session: DealerSession,
    delay: float,
    max_pages: int,
) -> IngestStats | None:
    """Fetch and ingest products from a dealer configured in dealers.yaml.

    Args:
        status: Provider status dict to update
        lock: Threading lock for safe updates
        cfg: Dealer configuration
        session: Authenticated dealer session
        delay: Delay between requests in seconds
        max_pages: Maximum pages to follow

    Returns:
        Ingestion statistics, or None if skipped
    """
    mapping_path = Path(cfg.mapping) if cfg.mapping else None
    if mapping_path is None or not mapping_path.exists():
        status["message"] = "missing mapping; skipping"
        status["state"] = "skipped"
        return None
    seeds = list(cfg.seeds.urls)
    if cfg.seeds.sitemap:
        seeds.extend(
            parse_sitemap_urls(
                cfg.seeds.sitemap,
                headers=None,
                limit=None,
                session=session.client,
            )
        )
    if not seeds:
        status["message"] = "no seeds configured; skipping"
        status["state"] = "skipped"
        return None
    status["total_seeds"] = len(seeds)
    products, offers = fetch_and_parse_urls(
        seeds,
        mapping_path,
        follow_next=True,
        max_pages=max_pages,
        delay_sec=delay,
        progress_cb=default_progress_cb(status, lock),
        session=session.client,
    )
    return upsert(products, offers)


def status_reporter(
    stop: threading.Event,
    statuses: dict[str, ProviderStatus],
    interval: int,
    lock: threading.Lock,
) -> None:
    """Background thread that periodically prints provider status as JSON.

    Args:
        stop: Event to signal thread stop
        statuses: Dict of provider statuses to report
        interval: Reporting interval in seconds
        lock: Threading lock for safe reads
    """
    while not stop.wait(interval):
        with lock:
            snapshot = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "providers": list(statuses.values()),
            }
        print(json.dumps(snapshot))


# --- CSV synthesis helpers ---


def group_offers_by_product(
    base_offers: list[OfferInput],
) -> dict[tuple[str, str], dict[str, float]]:
    """Group offers by (brand, mpn) with their base price.

    Args:
        base_offers: List of offers to group

    Returns:
        Dict mapping (brand, mpn) to price info
    """
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for offer in base_offers:
        key = (offer.brand, offer.mpn)
        grouped[key] = {"price": offer.price}
    return grouped


def generate_synthetic_offers(
    grouped: dict[tuple[str, str], dict[str, float]],
    suppliers: int,
    coverage: float,
    jitter: float,
    rng: random.Random,
) -> list[OfferInput]:
    """Generate synthetic offers for products.

    Args:
        grouped: Dict mapping (brand, mpn) to price info
        suppliers: Number of suppliers per product
        coverage: Fraction of products to synthesize (0.0-1.0)
        jitter: Max price variation +/- as fraction (0.0-0.5)
        rng: Random number generator

    Returns:
        List of synthetic offers
    """
    supplier_names = synthetic_supplier_names()
    extra_offers: list[OfferInput] = []
    for (brand, mpn), info in grouped.items():
        base_price = float(info.get("price", 0.0)) or 0.0
        if not should_synthesize_group(base_price, coverage, rng):
            continue
        extra_offers.extend(
            offers_for_group(
                brand,
                mpn,
                base_price,
                suppliers,
                jitter,
                rng,
                supplier_names,
            )
        )
    return extra_offers


def synthetic_supplier_names() -> list[str]:
    """Return list of synthetic supplier names.

    Returns:
        List of supplier name strings
    """
    return [
        "BiciPro",
        "RideLabs",
        "PedalX",
        "Velocita",
        "GearHub",
        "TrailWorks",
        "WheelHouse",
        "ChainLine",
    ]


def should_synthesize_group(
    base_price: float,
    coverage: float,
    rng: random.Random,
) -> bool:
    """Determine if a product group should have synthetic offers.

    Args:
        base_price: Base price of the product
        coverage: Target coverage fraction
        rng: Random number generator

    Returns:
        True if should synthesize, False otherwise
    """
    if rng.random() > coverage:
        return False
    if base_price <= 0:
        return False
    return True


def offers_for_group(
    brand: str,
    mpn: str,
    base_price: float,
    suppliers: int,
    jitter: float,
    rng: random.Random,
    supplier_names: list[str],
) -> list[OfferInput]:
    """Generate offers for a product group from random suppliers.

    Args:
        brand: Product brand
        mpn: Product MPN
        base_price: Base price to vary
        suppliers: Number of suppliers
        jitter: Max price variation fraction
        rng: Random number generator
        supplier_names: Pool of supplier names

    Returns:
        List of synthetic offers
    """
    extra_count = max(0, suppliers - 1)
    chosen = rng.sample(supplier_names, k=min(extra_count, len(supplier_names)))
    offers: list[OfferInput] = []
    for sup in chosen:
        price = synthetic_price(base_price, jitter, rng)
        in_stock = rng.random() < 0.7
        lead = rng.randint(0, 5)
        offers.append(
            OfferInput(
                brand=brand,
                mpn=mpn,
                supplier=sup,
                price=price,
                in_stock=in_stock,
                lead_time_days=lead,
            )
        )
    return offers


def synthetic_price(base_price: float, jitter: float, rng: random.Random) -> float:
    """Generate a synthetic price with random jitter.

    Args:
        base_price: Base price
        jitter: Max variation fraction
        rng: Random number generator

    Returns:
        Synthetic price rounded to 2 decimals
    """
    delta = rng.uniform(-jitter, jitter)
    return round(base_price * (1.0 + delta), 2)


def upsert_synthetic_offers(
    extra_offers: list[OfferInput], stats: IngestStats
) -> IngestStats:
    """Upsert synthetic offers and merge stats.

    Args:
        extra_offers: List of synthetic offers to upsert
        stats: Existing ingestion statistics

    Returns:
        Merged ingestion statistics
    """
    if not extra_offers:
        return stats
    stats2 = upsert([], extra_offers)
    return IngestStats(
        products_new=stats.products_new,
        products_updated=stats.products_updated,
        offers_upserted=stats.offers_upserted + stats2.offers_upserted,
        offers_skipped=stats.offers_skipped + stats2.offers_skipped,
    )


def compute_synth_summary() -> dict[str, int]:
    """Compute summary statistics for synthetic data.

    Returns:
        Dict with products, offers, suppliers, and in_stock_offers counts
    """
    with SessionLocal() as db:
        prod_count = int(
            db.scalar(select(func.count(func.distinct(SupplierOffer.product_id)))) or 0
        )
        offer_count = int(db.scalar(select(func.count(SupplierOffer.id))) or 0)
        sup_count = int(
            db.scalar(select(func.count(func.distinct(SupplierOffer.supplier)))) or 0
        )
        in_stock = int(
            db.scalar(
                select(func.count(SupplierOffer.id)).where(SupplierOffer.in_stock)
            )
            or 0
        )
    return {
        "products": prod_count,
        "offers": offer_count,
        "suppliers": sup_count,
        "in_stock_offers": in_stock,
    }
