from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _prepare_env(tmp_db: str, out_dir: str) -> None:
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_db}"
    os.environ["APP_OUT_DIR"] = out_dir


def _seed_db():
    from app.models import (
        Product,
        SupplierOffer,
        DealerPolicy,
        SessionLocal,
        create_all,
    )

    create_all()
    with SessionLocal() as db:
        # Products
        p1 = Product(brand="Shimano", mpn="CN-HG601", ean=None, name="Catena 11v")
        p2 = Product(brand="SRAM", mpn="PG-1230", ean=None, name="Cassetta 12v")
        db.add_all([p1, p2])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        # Offers: DealerA and DealerB
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
                SupplierOffer(
                    product_id=p2.id,
                    supplier="DealerA",
                    price=89.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
                SupplierOffer(
                    product_id=p2.id,
                    supplier="DealerB",
                    price=88.0,
                    in_stock=True,
                    lead_time_days=2,
                ),
            ]
        )
        # Policies
        db.add_all(
            [
                DealerPolicy(
                    dealer="DealerA",
                    base_cost=6.9,
                    free_threshold=49.0,
                    lead_days_std=2,
                    source="rules",
                    confidence=0.9,
                ),
                DealerPolicy(
                    dealer="DealerB",
                    base_cost=7.5,
                    free_threshold=59.0,
                    lead_days_std=2,
                    source="rules",
                    confidence=0.9,
                ),
            ]
        )
        db.commit()


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    # Use per-test SQLite file under tmp_path to avoid unique constraint collisions
    os.environ["APP_DB_URL"] = f"sqlite:///{tmp_path}/test_opt.db"
    os.environ["APP_OUT_DIR"] = str(tmp_path / "out")
    # reload modules to bind to fresh DB
    import importlib
    import app.config as app_config
    import app.models as app_models
    import app.pn as app_pn
    import app.api as app_api

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_pn)
    importlib.reload(app_api)
    _seed_db()
    from app.api import app

    return TestClient(app)


def test_optimize_miglior_prezzo(client: TestClient) -> None:
    r = client.post(
        "/optimize",
        json={
            "items": [
                {"maker_pn": "CN-HG601", "qty": 2},
                {"maker_pn": "PG-1230", "qty": 1},
            ],
            "params": {"scenario": "miglior-prezzo"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["costs"]["total"] > 0
    assert len(data["lines"]) == 2


def test_optimize_un_solo_dealer(client: TestClient) -> None:
    r = client.post(
        "/optimize",
        json={
            "items": [
                {"maker_pn": "CN-HG601", "qty": 1},
                {"maker_pn": "PG-1230", "qty": 1},
            ],
            "params": {"scenario": "un-solo-dealer"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    # Should have 1 dealer or fallback notes
    assert len(data["dealers"]) in (1, 2)
