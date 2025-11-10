import os
from pathlib import Path

import yaml


def test_synonyms():
    from app.search import apply_synonyms
    synonyms = yaml.safe_load(Path("app/synonyms.yaml").read_text(encoding="utf-8"))
    assert apply_synonyms("centerlock", "rotor", synonyms) == "CL"


def _setup_db(tmp_name: str):
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    # Import after setting env to pick up new DB URL
    from app.models import Product, SupplierOffer, SessionLocal, create_all

    create_all()
    return Product, SupplierOffer, SessionLocal


def test_ranking_stock_first():
    Product, SupplierOffer, SessionLocal = _setup_db("test_stock.db")

    with SessionLocal() as db:
        p = Product(brand="Test", mpn="A1", ean=None, name="Item", speed="11", brake="disc", axle="12x142", rotor="CL", freehub="HG")
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add_all(
            [
                SupplierOffer(product_id=p.id, supplier="S1", price=10.0, in_stock=True, lead_time_days=3),
                SupplierOffer(product_id=p.id, supplier="S2", price=10.0, in_stock=False, lead_time_days=1),
            ]
        )
        db.commit()

    from app.types import SearchRequest
    from app.search import search

    res = search(SearchRequest())
    assert res.items, "Expected results"
    assert res.items[0].in_stock is True, "In-stock offer should rank first at same price"


def test_compatibility_filter():
    Product, SupplierOffer, SessionLocal = _setup_db("test_compat.db")

    with SessionLocal() as db:
        p11 = Product(brand="T", mpn="M11", ean=None, name="11v", speed="11", brake="disc", axle="12x142", rotor="CL", freehub="HG")
        p12 = Product(brand="T", mpn="M12", ean=None, name="12v", speed="12", brake="disc", axle="12x142", rotor="CL", freehub="HG")
        db.add_all([p11, p12])
        db.commit()
        db.refresh(p11)
        db.refresh(p12)
        db.add_all(
            [
                SupplierOffer(product_id=p11.id, supplier="S", price=10.0, in_stock=True, lead_time_days=2),
                SupplierOffer(product_id=p12.id, supplier="S", price=12.0, in_stock=True, lead_time_days=2),
            ]
        )
        db.commit()

    from app.types import SearchRequest
    from app.search import search

    res = search(SearchRequest(speed="12"))
    assert all(item.mpn == "M12" for item in res.items), "Filter should exclude 11-speed items when 12 requested"

