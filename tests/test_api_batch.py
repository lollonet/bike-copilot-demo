from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _prepare_env(tmp_db: str, out_dir: str) -> None:
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_db}"
    os.environ["APP_OUT_DIR"] = out_dir


def _seed_db():
    from app.models import Product, SessionLocal, SupplierOffer, create_all

    create_all()
    with SessionLocal() as db:
        # P1
        p1 = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        db.add(p1)
        db.commit()
        db.refresh(p1)
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
                    product_id=p1.id,
                    supplier="DealerB",
                    price=23.5,
                    in_stock=False,
                    lead_time_days=3,
                ),
            ]
        )
        # P2
        p2 = Product(brand="SRAM", mpn="PG-1230", ean=None, name="Cassetta 12v")
        db.add(p2)
        db.commit()
        db.refresh(p2)
        db.add(
            SupplierOffer(
                product_id=p2.id,
                supplier="DealerA",
                price=89.0,
                in_stock=True,
                lead_time_days=2,
            )
        )
        db.commit()


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    _prepare_env("test_api_batch.db", str(tmp_path / "out"))
    # Reload modules to bind settings/SessionLocal to the fresh DB URL
    import importlib
    import app.config as app_config
    import app.models as app_models
    import app.pn as app_pn
    import app.api as app_api

    importlib.reload(app_config)
    importlib.reload(app_models)
    # Reload PN first so API can import fresh search_pn bound to new SessionLocal
    importlib.reload(app_pn)
    importlib.reload(app_api)
    _seed_db()
    from app.api import app

    return TestClient(app)


def test_search_pn_batch(client: TestClient) -> None:
    r = client.post(
        "/search_pn_batch",
        json={"items": ["CN-HG601", "PG-1230", "NOT-EXISTS"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 3
    by_pn = {res["maker_pn"]: res for res in data["results"]}
    assert by_pn["CN-HG601"]["offers"], "Expected offers for CN-HG601"
    assert by_pn["PG-1230"]["offers"], "Expected offers for PG-1230"
    assert by_pn["NOT-EXISTS"]["offers"] == []


def test_dealers(client: TestClient) -> None:
    r = client.get("/dealers")
    assert r.status_code == 200
    data = r.json()
    names = {d["name"] for d in data["dealers"]}
    assert {"DealerA", "DealerB"}.issubset(names)


def test_facets_endpoint_basic(client: TestClient) -> None:
    """Exercise /facets endpoint for a simple query; shape only."""
    r = client.post(
        "/facets",
        json={
            "query_text": "Catena",
            "speed": None,
            "freehub": None,
            "brake": None,
            "axle": None,
            "rotor": None,
            "budget_max": None,
            "category": None,
            "suppliers": [],
            "in_stock_only": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "totals" in data
    assert "products" in data["totals"]


def test_kpi_summary_endpoint_requires_auth(client: TestClient) -> None:
    """kpi/summary must enforce auth when basic credentials are configured."""
    r = client.get("/kpi/summary")
    assert r.status_code in (401, 403)


def test_kpi_summary_endpoint_shape_with_auth(client: TestClient) -> None:
    """Exercise /kpi/summary with auth for response shape."""
    auth = ("demo", "demo123")
    r = client.get("/kpi/summary", auth=auth)
    assert r.status_code == 200
    data = r.json()
    # Required top-level fields
    for key in [
        "products_total",
        "products_with_offers",
        "coverage_pn_pct",
        "offers_total",
        "offers_updated_24h",
        "updated_24h_pct",
        "pn_unmapped",
        "per_dealer",
    ]:
        assert key in data
    assert isinstance(data["per_dealer"], list)
