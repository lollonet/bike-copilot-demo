"""Tests for ingest CLI commands."""

from __future__ import annotations

import random
from pathlib import Path


def test_group_offers_by_product():
    """Test grouping offers by (brand, mpn)."""
    from app.cli_helpers.ingest_helpers import group_offers_by_product
    from app.types import OfferInput

    offers = [
        OfferInput(
            brand="Shimano",
            mpn="CS-M7100",
            supplier="Dealer1",
            price=89.99,
            in_stock=True,
            lead_time_days=2,
        ),
        OfferInput(
            brand="SRAM",
            mpn="PG-1230",
            supplier="Dealer2",
            price=120.00,
            in_stock=False,
            lead_time_days=5,
        ),
        OfferInput(
            brand="Shimano",
            mpn="CS-M7100",
            supplier="Dealer3",  # Duplicate product, different supplier
            price=85.00,
            in_stock=True,
            lead_time_days=1,
        ),
    ]

    grouped = group_offers_by_product(offers)

    # Should have 2 unique products (Shimano CS-M7100 appears twice but groups to one)
    assert len(grouped) == 2
    assert ("Shimano", "CS-M7100") in grouped
    assert ("SRAM", "PG-1230") in grouped

    # Last offer wins for duplicate products
    assert grouped[("Shimano", "CS-M7100")]["price"] == 85.00
    assert grouped[("SRAM", "PG-1230")]["price"] == 120.00


def test_synthetic_supplier_names():
    """Test that synthetic supplier names are returned."""
    from app.cli_helpers.ingest_helpers import synthetic_supplier_names

    names = synthetic_supplier_names()

    assert len(names) == 8
    assert "BiciPro" in names
    assert "RideLabs" in names
    assert "ChainLine" in names


def test_should_synthesize_group():
    """Test decision logic for synthesizing offers."""
    from app.cli_helpers.ingest_helpers import should_synthesize_group

    rng = random.Random(42)

    # Should not synthesize if price is 0 or negative
    assert not should_synthesize_group(0.0, 1.0, rng)
    assert not should_synthesize_group(-10.0, 1.0, rng)

    # Should synthesize with 100% coverage and valid price
    rng_always = random.Random(42)
    assert should_synthesize_group(100.0, 1.0, rng_always)

    # Should not synthesize with 0% coverage
    rng_never = random.Random(42)
    assert not should_synthesize_group(100.0, 0.0, rng_never)


def test_synthetic_price():
    """Test synthetic price generation with jitter."""
    from app.cli_helpers.ingest_helpers import synthetic_price

    rng = random.Random(42)
    base_price = 100.0
    jitter = 0.1  # ±10%

    # Generate several prices and check they're within jitter range
    prices = [synthetic_price(base_price, jitter, rng) for _ in range(10)]

    for price in prices:
        assert 90.0 <= price <= 110.0  # Within ±10% of base
        assert price != base_price  # Should be different from base

    # Check that prices are rounded to 2 decimals
    for price in prices:
        assert price == round(price, 2)


def test_offers_for_group():
    """Test generating synthetic offers for a product group."""
    from app.cli_helpers.ingest_helpers import (
        offers_for_group,
        synthetic_supplier_names,
    )

    rng = random.Random(42)
    supplier_names = synthetic_supplier_names()

    offers = offers_for_group(
        brand="Shimano",
        mpn="CS-M7100",
        base_price=100.0,
        suppliers=3,  # Should generate 2 extra (3-1)
        jitter=0.1,
        rng=rng,
        supplier_names=supplier_names,
    )

    # Should generate 2 extra offers (suppliers - 1)
    assert len(offers) == 2

    # Check offer properties
    for offer in offers:
        assert offer.brand == "Shimano"
        assert offer.mpn == "CS-M7100"
        assert offer.supplier in supplier_names
        assert 90.0 <= offer.price <= 110.0  # Within jitter range
        assert isinstance(offer.in_stock, bool)
        assert 0 <= offer.lead_time_days <= 5


def test_generate_synthetic_offers():
    """Test generating synthetic offers for multiple products."""
    from app.cli_helpers.ingest_helpers import generate_synthetic_offers

    grouped = {
        ("Shimano", "CS-M7100"): {"price": 100.0},
        ("SRAM", "PG-1230"): {"price": 120.0},
        ("Shimano", "XT-M8100"): {"price": 0.0},  # Should skip (price 0)
    }

    rng = random.Random(42)

    # Generate with high coverage
    extra_offers = generate_synthetic_offers(
        grouped=grouped,
        suppliers=3,
        coverage=1.0,  # 100% coverage
        jitter=0.1,
        rng=rng,
    )

    # Should generate offers for 2 products (skipping the 0-price one)
    # Each product gets 2 extra offers (suppliers - 1)
    assert len(extra_offers) >= 2  # At least some offers generated

    # Check that no offers were generated for 0-price product
    zero_price_offers = [o for o in extra_offers if o.mpn == "XT-M8100"]
    assert len(zero_price_offers) == 0


def test_upsert_synthetic_offers():
    """Test merging synthetic offer stats with existing stats."""
    from app.cli_helpers.ingest_helpers import upsert_synthetic_offers
    from app.ingest import IngestStats

    base_stats = IngestStats(
        products_new=10,
        products_updated=5,
        offers_upserted=20,
        offers_skipped=3,
    )

    # Test with empty offers - should return unchanged stats
    empty_result = upsert_synthetic_offers([], base_stats)
    assert empty_result.products_new == 10
    assert empty_result.products_updated == 5
    assert empty_result.offers_upserted == 20
    assert empty_result.offers_skipped == 3


def test_provider_lock_release():
    """Test provider lock creation and release."""
    from app.cli_helpers.ingest_helpers import provider_lock, release_lock
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        lock_dir = Path(tmpdir)

        # Create lock should succeed
        lock_file = provider_lock("test-provider", lock_dir)
        assert lock_file is not None
        assert lock_file.exists()

        # Creating same lock again should fail
        lock_file2 = provider_lock("test-provider", lock_dir)
        assert lock_file2 is None

        # Release lock
        release_lock(lock_file)
        assert not lock_file.exists()

        # Now creating lock again should succeed
        lock_file3 = provider_lock("test-provider", lock_dir)
        assert lock_file3 is not None
        assert lock_file3.exists()

        # Cleanup
        release_lock(lock_file3)


def test_load_dealer_seeds_missing():
    """Test loading dealer seeds for non-existent dealer."""
    from app.cli_helpers.ingest_helpers import load_dealer_seeds

    # Non-existent dealer should return empty list
    seeds = load_dealer_seeds("non-existent-dealer-xyz")
    assert seeds == []
