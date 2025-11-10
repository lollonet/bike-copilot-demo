import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _prepare_env(tmp_db: str, out_dir: str) -> None:
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_db}"
    os.environ["APP_OUT_DIR"] = out_dir
    os.environ["APP_BASIC_USER"] = "demo"
    os.environ["APP_BASIC_PASS"] = "demo123"


def _seed_db():
    from app.models import Product, SessionLocal, SupplierOffer, create_all

    create_all()
    with SessionLocal() as db:
        p = Product(
            brand="T",
            mpn="M1",
            ean=None,
            name="Test Item",
            speed="11",
            brake="disc",
            axle="12x142",
            rotor="CL",
            freehub="HG",
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        db.add(
            SupplierOffer(
                product_id=p.id,
                supplier="S",
                price=10.0,
                in_stock=True,
                lead_time_days=2,
            )
        )
        db.commit()


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _prepare_env("test_api.db", str(tmp_path / "out"))
    # Force HTML-only quotes
    import app.quote as q

    monkeypatch.setattr(q, "which", lambda _name: None, raising=False)

    from app.api import app  # import after env is set

    _seed_db()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "version" in data
    assert r.headers.get("X-Trace-Id")


def test_quote_requires_auth(client: TestClient) -> None:
    r = client.post(
        "/quote",
        json={
            "items": [{"offer_id": 1, "qty": 1}],
            "customer_name": "A",
            "customer_contact": "B",
        },
    )
    assert r.status_code in (401, 403)


def test_quote_and_files(client: TestClient) -> None:
    auth = ("demo", "demo123")
    r = client.post(
        "/quote",
        auth=auth,
        json={
            "items": [{"offer_id": 1, "qty": 2}],
            "customer_name": "A",
            "customer_contact": "B",
            "validity_days": 7,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["content_type"] == "text/html"
    html_path = data["html_path"]
    assert Path(html_path).exists()
    # Retrieve via /files
    name = Path(html_path).name
    fr = client.get(f"/files/{name}", auth=auth)
    assert fr.status_code == 200
    # Block non-allowed extension
    fr2 = client.get("/files/README.md", auth=auth)
    assert fr2.status_code == 404
