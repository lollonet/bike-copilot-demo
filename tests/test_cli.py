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
            "--qty",
            "2",
            "--customer-name",
            "Mario",
            "--customer-contact",
            "mario@example.com",
        ],
    )
    assert result.exit_code == 0
    assert "html_path" in result.stdout


def test_ingest_csv_mapped_cli(runner: CliRunner, tmp_path: Path) -> None:
    """Exercise ingest-csv-mapped wiring end-to-end."""
    from app.cli import app

    csv_path = tmp_path / "demo.csv"
    csv_path.write_text(
        "Codice;Categoria;Descrizione;Prezzo\n"
        "C1;Catena MTB;Catena 11v;10,50\n",
        encoding="utf-8",
    )
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(
        "\n".join(
            [
                "supplier: DemoDealer",
                'delimiter: ";"',
                "columns:",
                "  mpn: Codice",
                "  category: Categoria",
                "  name: Descrizione",
                "  price: Prezzo",
                "defaults:",
                "  in_stock: true",
                "  lead_time_days: 2",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "ingest-csv-mapped",
            "--csv",
            str(csv_path),
            "--mapping",
            str(mapping_path),
        ],
    )
    assert result.exit_code == 0
    # CLI prints the IngestStats dataclass; ensure it reports the expected counts.
    out = result.stdout
    assert "IngestStats" in out
    assert "offers_upserted=1" in out


def test_ingest_csv_synth_cli(runner: CliRunner, tmp_path: Path) -> None:
    """Exercise ingest-csv-synth wiring and summary output."""
    from app.cli import app

    csv_path = tmp_path / "demo_synth.csv"
    csv_path.write_text(
        "Codice;Categoria;Descrizione;Prezzo\n"
        "C1;Catena MTB;Catena 11v;10,50\n",
        encoding="utf-8",
    )
    mapping_path = tmp_path / "mapping_synth.yaml"
    mapping_path.write_text(
        "\n".join(
            [
                "supplier: DemoDealer",
                'delimiter: ";"',
                "columns:",
                "  mpn: Codice",
                "  category: Categoria",
                "  name: Descrizione",
                "  price: Prezzo",
                "defaults:",
                "  in_stock: true",
                "  lead_time_days: 2",
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "ingest-csv-synth",
            "--csv",
            str(csv_path),
            "--mapping",
            str(mapping_path),
            "--suppliers",
            "2",
            "--coverage",
            "1.0",
            "--jitter",
            "0.0",
        ],
    )
    assert result.exit_code == 0
    # Summary dict should include suppliers and ingest keys.
    assert "suppliers" in result.stdout


def test_fetch_policy_cli(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise fetch-policy wiring without real HTTP."""
    from app.cli import app

    # Fake HTTP response and parser
    import httpx
    from app.policy import PolicyExtract

    class DummyResp:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(self, timeout: float, headers: dict[str, str], follow_redirects: bool):
            self._timeout = timeout
            self._headers = headers
            self._follow = follow_redirects

        def get(self, url: str) -> DummyResp:
            return DummyResp("<html>dummy</html>")

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(httpx, "Client", DummyClient, raising=False)

    import app.cli as app_cli

    def fake_parse_policy_html(html: str) -> PolicyExtract:
        return PolicyExtract(
            base_cost=6.9,
            free_threshold=49.0,
            lead_days_std=2,
            confidence=0.9,
        )

    monkeypatch.setattr(app_cli, "parse_policy_html", fake_parse_policy_html, raising=False)

    result = runner.invoke(
        app,
        [
            "fetch-policy",
            "--dealer",
            "DemoDealer",
            "--url",
            "https://example.com/policy",
        ],
    )
    assert result.exit_code == 0
    out = result.stdout
    assert "DemoDealer" in out
    assert "base_cost" in out


def test_fetch_web_url_cli(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise fetch-web-url wiring with synthetic HTML and mapping."""
    from app.cli import app

    # Prepare a mapping YAML compatible with web_adapter.parse_html
    mapping_yaml = tmp_path / "web_map.yaml"
    mapping_yaml.write_text(
        "\n".join(
            [
                "supplier: DemoWeb",
                "root: .item",
                "brand: .brand",
                "mpn: .mpn",
                "name: .name",
                "price: .price",
            ]
        ),
        encoding="utf-8",
    )

    # Seed HTML for one URL
    html = """
    <html><body>
      <div class="item">
        <span class="brand">Shimano</span>
        <span class="mpn">C1</span>
        <span class="name">Catena 11v</span>
        <span class="price">10,50 €</span>
      </div>
    </body></html>
    """

    import httpx

    class DummyResp:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(self, timeout: float, headers: dict[str, str], follow_redirects: bool):
            self._timeout = timeout
            self._headers = headers
            self._follow = follow_redirects

        def get(self, url: str) -> DummyResp:
            return DummyResp(html)

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(httpx, "Client", DummyClient, raising=False)

    result = runner.invoke(
        app,
        [
            "fetch-web-url",
            "--url",
            "https://shop.example/seed",
            "--mapping",
            str(mapping_yaml),
        ],
    )
    assert result.exit_code == 0
    # Summary dict printed should include at least products/offers/ingest keys.
    out = result.stdout
    assert "offers" in out
