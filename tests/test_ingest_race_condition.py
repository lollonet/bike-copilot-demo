"""Test for RACE-001: Price history race condition (issue #45).

This test verifies that when a batch contains the same offer with different prices,
all price changes are recorded in the price history.
"""

from __future__ import annotations

import os
from pathlib import Path
import importlib
from sqlalchemy import select, func

from app.types import ProductInput, OfferInput


def _setup_db(tmp_name: str):
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    # Reload modules so SessionLocal and ingest bind to the fresh DB URL
    import app.config as app_config
    import app.models as app_models
    import app.ingest as app_ingest

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_ingest)
    from app.models import (
        Product,
        SupplierOffer,
        PriceHistory,
        SessionLocal,
        create_all,
    )

    # Ensure a clean file for repeated runs
    db_file = Path(tmp_name)
    for suffix in ("", "-shm", "-wal"):
        p = db_file.with_name(db_file.name + suffix)
        if p.exists():
            p.unlink()

    create_all()
    return Product, SupplierOffer, PriceHistory, SessionLocal


def test_batch_with_multiple_price_changes_for_same_offer():
    """Test that multiple price changes in same batch all create history entries.

    Reproduces RACE-001: When batch contains:
    - Row 1: price=100 → 150 (creates history ✓)
    - Row 2: price=150 → 200 (NO history created ❌)

    This test verifies the fix ensures BOTH price changes are recorded.
    """
    from app.ingest import upsert

    Product, SupplierOffer, PriceHistory, SessionLocal = _setup_db(
        "test_race_condition.db"
    )

    # Create initial product and offer with price=100
    products_initial = [
        ProductInput(
            brand="Shimano",
            mpn="CN-HG601",
            ean=None,
            name="Chain 11v",
            category="transmission",
            speed=None,
            brake=None,
            freehub=None,
            axle=None,
            rotor=None,
        )
    ]
    offers_initial = [
        OfferInput(
            brand="Shimano",
            mpn="CN-HG601",
            supplier="test-supplier",
            price=100.0,
            in_stock=True,
            lead_time_days=None,
            dealer_code=None,
        )
    ]

    # First batch: create product and offer with price=100
    upsert(products_initial, offers_initial)

    # Verify initial state
    with SessionLocal() as db:
        offer = db.scalar(
            select(SupplierOffer).where(SupplierOffer.supplier == "test-supplier")
        )
        assert offer is not None
        assert offer.price == 100.0

        # No price history yet (first price)
        history_count = db.scalar(select(func.count()).select_from(PriceHistory))
        assert history_count == 0

    # Second batch: Two rows with same offer but different prices
    # This simulates receiving the same product from a feed twice with price changes
    products_batch = [
        ProductInput(
            brand="Shimano",
            mpn="CN-HG601",
            ean=None,
            name="Chain 11v",
            category="transmission",
            speed=None,
            brake=None,
            freehub=None,
            axle=None,
            rotor=None,
        ),
        ProductInput(
            brand="Shimano",
            mpn="CN-HG601",
            ean=None,
            name="Chain 11v",
            category="transmission",
            speed=None,
            brake=None,
            freehub=None,
            axle=None,
            rotor=None,
        ),
    ]
    offers_batch = [
        # Row 1: price change from 100 to 150
        OfferInput(
            brand="Shimano",
            mpn="CN-HG601",
            supplier="test-supplier",
            price=150.0,
            in_stock=True,
            lead_time_days=None,
            dealer_code=None,
        ),
        # Row 2: price change from 150 to 200
        OfferInput(
            brand="Shimano",
            mpn="CN-HG601",
            supplier="test-supplier",
            price=200.0,
            in_stock=True,
            lead_time_days=None,
            dealer_code=None,
        ),
    ]

    # Process the batch
    upsert(products_batch, offers_batch)

    # Verify both price changes were recorded
    with SessionLocal() as db:
        offer = db.scalar(
            select(SupplierOffer).where(SupplierOffer.supplier == "test-supplier")
        )
        assert offer is not None
        assert offer.price == 200.0, "Final price should be 200"

        # Check price history: should have 2 entries (100→150 and 150→200)
        history_entries = db.scalars(
            select(PriceHistory)
            .where(PriceHistory.offer_id == offer.id)
            .order_by(PriceHistory.ts)
        ).all()

        assert len(history_entries) == 2, (
            f"Expected 2 price history entries, got {len(history_entries)}. "
            f"Prices: {[e.price for e in history_entries]}"
        )

        # Verify the price values in history
        assert history_entries[0].price == 150.0, "First change should be to 150"
        assert history_entries[1].price == 200.0, "Second change should be to 200"


def test_batch_with_same_price_does_not_create_duplicate_history():
    """Test that processing same offer with same price doesn't create history entry."""
    from app.ingest import upsert

    Product, SupplierOffer, PriceHistory, SessionLocal = _setup_db(
        "test_no_duplicate_history.db"
    )

    # Create initial product and offer
    products = [
        ProductInput(
            brand="SRAM",
            mpn="XX1-EAGLE",
            ean=None,
            name="Cassette",
            category="transmission",
            speed=None,
            brake=None,
            freehub=None,
            axle=None,
            rotor=None,
        )
    ]
    offers = [
        OfferInput(
            brand="SRAM",
            mpn="XX1-EAGLE",
            supplier="test-supplier",
            price=300.0,
            in_stock=True,
            lead_time_days=None,
            dealer_code=None,
        )
    ]

    upsert(products, offers)

    # Process same offer again with same price
    upsert(products, offers)

    with SessionLocal() as db:
        offer = db.scalar(
            select(SupplierOffer).where(SupplierOffer.supplier == "test-supplier")
        )
        assert offer is not None

        # Should have NO history entries (price didn't change)
        history_count = db.scalar(
            select(func.count())
            .select_from(PriceHistory)
            .where(PriceHistory.offer_id == offer.id)
        )
        assert history_count == 0, (
            "No history should be created when price doesn't change"
        )
