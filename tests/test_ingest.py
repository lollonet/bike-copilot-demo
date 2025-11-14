from __future__ import annotations

import os
from pathlib import Path
import importlib

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
        PNMapping,
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
    return Product, SupplierOffer, PriceHistory, PNMapping, SessionLocal


def test_upsert_creates_product_offer_and_mapping():
    from app.ingest import upsert

    (
        Product,
        SupplierOffer,
        PriceHistory,  # noqa: F401
        PNMapping,
        SessionLocal,
    ) = _setup_db("test_ingest.db")

    core = [
        ProductInput(
            brand="Shimano",
            mpn="CN-HG601",
            ean=None,
            name="Catena 11v",
            category="trasmissione mtb",
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
            supplier="DealerA",
            price=24.9,
            in_stock=True,
            lead_time_days=1,
            currency="EUR",
            extra={"dealer_pn": "ICNHG601116"},
        )
    ]

    stats = upsert(core, offers)
    assert stats.products_new == 1
    assert stats.products_updated == 0
    assert stats.offers_upserted == 1
    assert stats.offers_skipped == 0

    with SessionLocal() as db:
        products = db.query(Product).all()
        offers_db = db.query(SupplierOffer).all()
        mappings = db.query(PNMapping).all()
        assert len(products) == 1
        assert len(offers_db) == 1
        assert len(mappings) == 1
        assert mappings[0].dealer == "DealerA"


def test_upsert_updates_price_and_history():
    from app.ingest import upsert

    (
        Product,
        SupplierOffer,
        PriceHistory,
        PNMapping,  # noqa: F401
        SessionLocal,
    ) = _setup_db("test_ingest2.db")

    core = [
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
    first_offer = OfferInput(
        brand="Shimano",
        mpn="CN-HG601",
        supplier="DealerA",
        price=24.9,
        in_stock=True,
        lead_time_days=1,
        currency="EUR",
        extra={},
    )
    second_offer = OfferInput(
        brand="Shimano",
        mpn="CN-HG601",
        supplier="DealerA",
        price=23.5,
        in_stock=True,
        lead_time_days=2,
        currency="EUR",
        extra={},
    )

    upsert(core, [first_offer])
    upsert(core, [second_offer])

    with SessionLocal() as db:
        offers_db = db.query(SupplierOffer).all()
        history = db.query(PriceHistory).all()
        assert len(offers_db) == 1
        assert offers_db[0].price == 23.5
        assert len(history) == 1
        assert history[0].price == 23.5


def test_upsert_skips_offers_without_product():
    from app.ingest import upsert

    (
        Product,
        SupplierOffer,
        PriceHistory,  # noqa: F401
        PNMapping,  # noqa: F401
        SessionLocal,
    ) = _setup_db("test_ingest3.db")

    core: list[ProductInput] = []
    offers = [
        OfferInput(
            brand="Unknown",
            mpn="NO-MATCH",
            supplier="DealerX",
            price=10.0,
            in_stock=True,
            lead_time_days=None,
            currency=None,
            extra={},
        )
    ]

    stats = upsert(core, offers)
    assert stats.products_new == 0
    assert stats.offers_upserted == 0
    assert stats.offers_skipped == 1

    with SessionLocal() as db:
        assert db.query(Product).count() == 0
        assert db.query(SupplierOffer).count() == 0


def test_upsert_deduplicates_offers_in_single_batch():
    from app.ingest import upsert

    (
        Product,  # noqa: F401
        SupplierOffer,
        PriceHistory,
        PNMapping,  # noqa: F401
        SessionLocal,
    ) = _setup_db("test_ingest4.db")

    core = [
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
            supplier="DealerA",
            price=24.9,
            in_stock=True,
            lead_time_days=1,
            currency="EUR",
            extra={},
        ),
        OfferInput(
            brand="Shimano",
            mpn="CN-HG601",
            supplier="DealerA",
            price=23.5,
            in_stock=False,
            lead_time_days=2,
            currency="EUR",
            extra={},
        ),
    ]

    stats = upsert(core, offers)
    assert stats.offers_upserted == 2
    assert stats.offers_skipped == 0

    with SessionLocal() as db:
        offers_db = db.query(SupplierOffer).all()
        history = db.query(PriceHistory).all()
        assert len(offers_db) == 1
        assert offers_db[0].price == 23.5
        assert offers_db[0].in_stock is False
        assert offers_db[0].lead_time_days == 2
        assert history == []
