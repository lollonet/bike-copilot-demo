from __future__ import annotations

import os
from pathlib import Path


def _setup_db(tmp_name: str):
    """Prepare an isolated SQLite DB for this test run.

    Removes any existing file to avoid UNIQUE constraint issues across repeated runs.
    """
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    db_file = Path(tmp_name)
    for suffix in ("", "-shm", "-wal"):
        p = db_file.with_name(db_file.name + suffix)
        if p.exists():
            p.unlink()

    import importlib
    import app.config as app_config
    import app.models as app_models
    import app.pn as app_pn

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_pn)
    from app.models import Product, SupplierOffer, PNMapping, SessionLocal, create_all

    create_all()
    return Product, SupplierOffer, PNMapping, SessionLocal


def test_pn_mapping_dealer_code_lookup():
    Product, SupplierOffer, PNMapping, SessionLocal = _setup_db("test_pn_map.db")
    with SessionLocal() as db:
        p = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        db.add(p)
        db.commit()
        db.refresh(p)
        # Offer exists for the product
        db.add(
            SupplierOffer(
                product_id=p.id,
                supplier="DealerA",
                price=24.9,
                in_stock=True,
                lead_time_days=1,
            )
        )
        # Alias maps dealer code to maker PN
        db.add(
            PNMapping(
                product_id=p.id,
                dealer="DealerA",
                maker_pn_norm="CNHG601",
                dealer_pn_norm="ICNHG601116",
                confidence=0.98,
            )
        )
        db.commit()

    from app.types import SearchPNRequest
    from app.pn import search_pn

    # Searching by dealer code should resolve to the product via mapping
    res = search_pn(SearchPNRequest(maker_pn="ICN-HG601-116"))
    assert res.offers and res.offers[0].dealer == "DealerA"


def test_pn_mapping_updates_on_same_dealer_code():
    # Same dealer code should be updated to point to a new product, not duplicated
    Product, SupplierOffer, PNMapping, SessionLocal = _setup_db("test_pn_map2.db")
    with SessionLocal() as db:
        p1 = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        p2 = Product(brand="Shimano", mpn="CN-HG701", ean=None, name="Catena 12v")
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        db.add(
            SupplierOffer(
                product_id=p1.id, supplier="DealerA", price=24.9, in_stock=True
            )
        )
        db.add(
            SupplierOffer(
                product_id=p2.id, supplier="DealerA", price=29.9, in_stock=True
            )
        )
        # Initial mapping for DealerA code → CN-HG601
        db.add(
            PNMapping(
                product_id=p1.id,
                dealer="DealerA",
                maker_pn_norm="CNHG601",
                dealer_pn_norm="ICNHG601116",
                confidence=0.9,
            )
        )
        db.commit()

    # Re-import YAML that remaps same dealer code to CN-HG701
    from tempfile import NamedTemporaryFile
    from pathlib import Path

    yml = """
- dealer: DealerA
  aliases:
    - maker_pn: CN-HG701
      dealer_pn: ICNHG601116
      confidence: 0.95
""".strip()
    with NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f:
        f.write(yml)
        temp_path = Path(f.name)

    # Reload CLI bound to current DB and import
    import importlib
    import app.cli as app_cli

    importlib.reload(app_cli)
    from app.cli import pn_alias_import

    pn_alias_import(temp_path)

    with SessionLocal() as db:
        rows = (
            db.query(PNMapping)
            .filter(
                PNMapping.dealer == "DealerA", PNMapping.dealer_pn_norm == "ICNHG601116"
            )
            .all()
        )
        assert len(rows) == 1, "Expected single mapping per dealer code"
        row = rows[0]
        # It should now point to the CN-HG701 product
        prod = db.query(Product).filter(Product.id == row.product_id).first()
        assert prod and prod.mpn == "CN-HG701"
