from __future__ import annotations

import os


def _setup_db(tmp_name: str):
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    import importlib
    import app.config as app_config
    import app.models as app_models
    importlib.reload(app_config)
    importlib.reload(app_models)
    from app.models import Product, SupplierOffer, PNMapping, SessionLocal, create_all
    create_all()
    return Product, SupplierOffer, PNMapping, SessionLocal


def test_pn_mapping_dealer_code_lookup():
    Product, SupplierOffer, PNMapping, SessionLocal = _setup_db("test_pn_map.db")
    with SessionLocal() as db:
        p = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        db.add(p); db.commit(); db.refresh(p)
        # Offer exists for the product
        db.add(SupplierOffer(product_id=p.id, supplier="DealerA", price=24.9, in_stock=True, lead_time_days=1))
        # Alias maps dealer code to maker PN
        db.add(PNMapping(product_id=p.id, dealer="DealerA", maker_pn_norm="CNHG601", dealer_pn_norm="ICNHG601116", confidence=0.98))
        db.commit()

    from app.types import SearchPNRequest
    from app.pn import search_pn

    # Searching by dealer code should resolve to the product via mapping
    res = search_pn(SearchPNRequest(maker_pn="ICN-HG601-116"))
    assert res.offers and res.offers[0].dealer == "DealerA"

