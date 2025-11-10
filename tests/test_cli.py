import os
from pathlib import Path

import pytest
from typer.testing import CliRunner


def _prepare_env(tmp_db: str, out_dir: str) -> None:
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_db}"
    os.environ["APP_OUT_DIR"] = out_dir


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
        db.add(SupplierOffer(product_id=p.id, supplier="S", price=10.0, in_stock=True, lead_time_days=2))
        db.commit()


@pytest.fixture()
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    _prepare_env("test_cli.db", str(tmp_path / "out"))
    # Force HTML-only quotes
    import app.quote as q

    monkeypatch.setattr(q, "which", lambda _name: None, raising=False)
    _seed_db()
    return CliRunner()


def test_search_cli(runner: CliRunner) -> None:
    from app.cli import app

    result = runner.invoke(app, ["search-cli", "--speed", "11", "--freehub", "HG"])
    assert result.exit_code == 0
    assert "Top 3 Offers" in result.stdout


def test_quote_cli(runner: CliRunner, tmp_path: Path) -> None:
    from app.cli import app

    result = runner.invoke(
        app,
        [
            "quote-cli",
            "--offer-id",
            "1",
            "--customer-name",
            "Mario",
            "--customer-contact",
            "mario@example.com",
        ],
    )
    assert result.exit_code == 0
    assert "html_path" in result.stdout

