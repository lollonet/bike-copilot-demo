import os
from pathlib import Path
import importlib

import yaml


def test_synonyms():
    from app.search import apply_synonyms

    synonyms = yaml.safe_load(Path("app/synonyms.yaml").read_text(encoding="utf-8"))
    assert apply_synonyms("centerlock", "rotor", synonyms) == "CL"


def _setup_db(tmp_name: str):
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    # Reload config and models so SessionLocal binds to the fresh DB URL
    import app.config as app_config
    import app.models as app_models
    import app.search as app_search

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_search)
    from app.models import Product, SupplierOffer, SessionLocal, create_all

    create_all()
    return Product, SupplierOffer, SessionLocal


def test_ranking_stock_first():
    Product, SupplierOffer, SessionLocal = _setup_db("test_stock.db")

    with SessionLocal() as db:
        p = Product(
            brand="Test",
            mpn="A1",
            ean=None,
            name="Item",
            speed="11",
            brake="disc",
            axle="12x142",
            rotor="CL",
            freehub="HG",
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add_all(
            [
                SupplierOffer(
                    product_id=p.id,
                    supplier="S1",
                    price=10.0,
                    in_stock=True,
                    lead_time_days=3,
                ),
                SupplierOffer(
                    product_id=p.id,
                    supplier="S2",
                    price=10.0,
                    in_stock=False,
                    lead_time_days=1,
                ),
            ]
        )
        db.commit()

    from app.types import SearchRequest
    from app.search import search

    res = search(SearchRequest())
    assert res.items, "Expected results"
    assert res.items[0].in_stock is True, (
        "In-stock offer should rank first at same price"
    )


def test_compatibility_filter():
    Product, SupplierOffer, SessionLocal = _setup_db("test_compat.db")

    with SessionLocal() as db:
        p11 = Product(
            brand="T",
            mpn="M11",
            ean=None,
            name="11v",
            speed="11",
            brake="disc",
            axle="12x142",
            rotor="CL",
            freehub="HG",
        )
        p12 = Product(
            brand="T",
            mpn="M12",
            ean=None,
            name="12v",
            speed="12",
            brake="disc",
            axle="12x142",
            rotor="CL",
            freehub="HG",
        )
        db.add_all([p11, p12])
        db.commit()
        db.refresh(p11)
        db.refresh(p12)
        db.add_all(
            [
                SupplierOffer(
                    product_id=p11.id,
                    supplier="S",
                    price=10.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
                SupplierOffer(
                    product_id=p12.id,
                    supplier="S",
                    price=12.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
            ]
        )
        db.commit()

    from app.types import SearchRequest
    from app.search import search

    res = search(SearchRequest(speed="12"))
    assert all(item.mpn == "M12" for item in res.items), (
        "Filter should exclude 11-speed items when 12 requested"
    )


def test_category_canonicalization_match():
    # Ensure canonicalized facet label (title-cased) matches raw stored category
    Product, SupplierOffer, SessionLocal = _setup_db("test_category.db")

    with SessionLocal() as db:
        p = Product(
            brand="T",
            mpn="C1",
            ean=None,
            name="Catena",
            category="trasmissione mtb",  # raw lowercase with space
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add(
            SupplierOffer(
                product_id=p.id,
                supplier="S",
                price=9.99,
                in_stock=True,
                lead_time_days=1,
            )
        )
        db.commit()

    from app.types import SearchRequest
    from app.search import search

    # Category as it would appear in facet labels
    res = search(SearchRequest(category="Trasmissione Mtb"))
    assert res.items, "Expected results to match canonicalized category label"
    assert any(it.mpn == "C1" for it in res.items), "Should include product C1"


def test_facets_apply_budget_and_supplier_filters():
    """Facets must respect budget_max and suppliers filters when counting offers."""
    Product, SupplierOffer, SessionLocal = _setup_db("test_facets.db")

    with SessionLocal() as db:
        p = Product(
            brand="Shimano",
            mpn="C1",
            ean=None,
            name="Catena 11v",
            category="Catene",
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add_all(
            [
                SupplierOffer(
                    product_id=p.id,
                    supplier="DealerA",
                    price=10.0,
                    in_stock=True,
                    lead_time_days=1,
                ),
                SupplierOffer(
                    product_id=p.id,
                    supplier="DealerB",
                    price=20.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
            ]
        )
        db.commit()

    from app.types import SearchRequest
    from app.search import facets

    # With budget_max=15 and suppliers=["DealerA"], only DealerA offer should count.
    req = SearchRequest(
        budget_max=15.0,
        suppliers=["DealerA"],
        in_stock_only=True,
    )
    res = facets(req)
    # Supplier counts must include only DealerA after filters.
    assert res.supplier.get("DealerA", 0) >= 1
    assert res.supplier.get("DealerB", 0) == 0
