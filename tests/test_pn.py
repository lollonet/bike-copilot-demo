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


def test_search_pn_batch_preserves_order_and_duplicates():
    Product, SupplierOffer, SessionLocal = _setup_db("test_pn_batch.db")
    with SessionLocal() as db:
        p1 = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        p2 = Product(brand="SRAM", mpn="PG-1230", ean=None, name="Cassetta 12v")
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        db.add_all(
            [
                SupplierOffer(
                    product_id=p1.id,
                    supplier="DealerA",
                    price=24.9,
                    in_stock=True,
                    lead_time_days=1,
                ),
                SupplierOffer(
                    product_id=p2.id,
                    supplier="DealerB",
                    price=89.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
            ]
        )
        db.commit()

    from app.types import SearchPNBatchRequest
    from app.pn import search_pn_batch

    req = SearchPNBatchRequest(
        items=["CN-HG601", "PG-1230", "CN-HG601", "UNKNOWN"],
        dealers=None,
        in_stock_only=None,
    )
    res = search_pn_batch(req)
    # The order and multiplicity of input items must be preserved
    assert [r.maker_pn for r in res.results] == [
        "CN-HG601",
        "PG-1230",
        "CN-HG601",
        "UNKNOWN",
    ]
    # Offers exist only for known PNs
    counts = [len(r.offers) for r in res.results]
    assert counts[0] >= 1 and counts[1] >= 1 and counts[2] >= 1 and counts[3] == 0
