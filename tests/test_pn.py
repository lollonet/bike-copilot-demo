from __future__ import annotations

import os


def _setup_db(tmp_name: str):
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    # Reload config and models so that settings.db_url and SessionLocal rebind
    import importlib
    import app.config as app_config
    import app.models as app_models
    import app.pn as app_pn

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_pn)
    from app.models import Product, SupplierOffer, SessionLocal, create_all

    create_all()
    return Product, SupplierOffer, SessionLocal


def test_search_pn_normalization_match():
    Product, SupplierOffer, SessionLocal = _setup_db("test_pn.db")

    with SessionLocal() as db:
        p = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add(
            SupplierOffer(
                product_id=p.id,
                supplier="DealerA",
                price=24.9,
                in_stock=True,
                lead_time_days=1,
            )
        )
        db.commit()

    from app.types import SearchPNRequest
    from app.pn import search_pn

    res = search_pn(SearchPNRequest(maker_pn="CNHG601"))
    assert res.offers and res.offers[0].dealer == "DealerA"


def test_search_pn_filters_and_sort():
    Product, SupplierOffer, SessionLocal = _setup_db("test_pn2.db")
    with SessionLocal() as db:
        p = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add_all(
            [
                SupplierOffer(
                    product_id=p.id,
                    supplier="DealerA",
                    price=25.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
                SupplierOffer(
                    product_id=p.id,
                    supplier="DealerB",
                    price=23.0,
                    in_stock=False,
                    lead_time_days=1,
                ),
            ]
        )
        db.commit()

    from app.types import SearchPNRequest
    from app.pn import search_pn

    # In-stock should come first despite slightly higher price
    res = search_pn(SearchPNRequest(maker_pn="CN-HG601"))
    assert res.offers and res.offers[0].dealer == "DealerA"
    # Filter dealers
    res2 = search_pn(SearchPNRequest(maker_pn="CN-HG601", dealers=["DealerB"]))
    assert res2.offers, "Expected filtered offers for DealerB"
    assert all(o.dealer == "DealerB" for o in res2.offers)
