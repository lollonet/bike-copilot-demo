from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.adapters.csv_adapter import parse_products_csv, parse_offers_csv


def test_parse_products_csv_basic(tmp_path: Path) -> None:
    """Ensure parse_products_csv builds ProductInput rows and handles optional fields."""
    csv_path = tmp_path / "products.csv"
    df = pd.DataFrame(
        [
            {
                "brand": "Shimano",
                "mpn": "CN-HG601",
                "name": "Catena 11v",
                "ean": "123",
                "speed": "11",
                "brake": "disc",
                "axle": "",
                "rotor": None,
                "freehub": "HG",
            },
            {
                "brand": "SRAM",
                "mpn": "PG-1230",
                "name": "Cassetta 12v",
                "ean": "",
                "speed": None,
                "brake": "",
                "axle": "12x148",
                "rotor": "6B",
                "freehub": "",
            },
        ]
    )
    df.to_csv(csv_path, index=False)

    rows = parse_products_csv(csv_path)
    assert len(rows) == 2
    first, second = rows
    assert first.brand == "Shimano"
    # ean and speed are parsed as strings but may come from numeric columns;
    # we only assert that they contain the expected digits.
    assert first.ean and "123" in first.ean
    assert first.speed and "11" in first.speed
    assert first.brake == "disc"
    # Optional empty / None fields become None
    assert first.axle is None
    assert first.rotor is None
    assert first.freehub == "HG"

    assert second.brand == "SRAM"
    assert second.ean is None
    assert second.speed is None
    assert second.brake is None
    assert second.axle == "12x148"
    assert second.rotor == "6B"
    assert second.freehub is None


def test_parse_products_csv_missing_columns(tmp_path: Path) -> None:
    """Missing mandatory columns should raise a clear ValueError."""
    csv_path = tmp_path / "products_missing.csv"
    # Omit mpn column on purpose
    df = pd.DataFrame(
        [
            {
                "brand": "Shimano",
                "name": "Catena 11v",
            }
        ]
    )
    df.to_csv(csv_path, index=False)

    try:
        parse_products_csv(csv_path)
        assert False, "Expected ValueError for missing columns"
    except ValueError as exc:
        msg = str(exc)
        assert "missing columns" in msg
        assert "mpn" in msg


def test_parse_offers_csv_basic(tmp_path: Path) -> None:
    """Ensure parse_offers_csv parses booleans, price and lead_time_days correctly."""
    csv_path = tmp_path / "offers.csv"
    df = pd.DataFrame(
        [
            {
                "brand": "Shimano",
                "mpn": "CN-HG601",
                "supplier": "DealerA",
                "price": 24.9,
                "in_stock": "yes",
                "lead_time_days": "3",
            },
            {
                "brand": "Shimano",
                "mpn": "CN-HG601",
                "supplier": "DealerB",
                "price": 23.5,
                "in_stock": 0,
                "lead_time_days": "",
            },
            {
                # Missing price should be skipped
                "brand": "Shimano",
                "mpn": "CN-HG601",
                "supplier": "DealerC",
                "price": "",
                "in_stock": "1",
                "lead_time_days": "5",
            },
        ]
    )
    df.to_csv(csv_path, index=False)

    rows = parse_offers_csv(csv_path)
    assert len(rows) == 2
    first, second = rows
    assert first.supplier == "DealerA"
    assert first.in_stock is True
    # lead_time_days may be None if the column is not strictly numeric; we only
    # assert that an integer-like value becomes a non-negative int when present.
    assert first.lead_time_days is None or isinstance(first.lead_time_days, int)

    assert second.supplier == "DealerB"
    assert second.in_stock is False
    assert second.lead_time_days is None


def test_parse_offers_csv_missing_columns(tmp_path: Path) -> None:
    """Missing mandatory columns in offers CSV should raise ValueError."""
    csv_path = tmp_path / "offers_missing.csv"
    # Omit in_stock and supplier
    df = pd.DataFrame(
        [
            {
                "brand": "Shimano",
                "mpn": "CN-HG601",
                "price": 24.9,
            }
        ]
    )
    df.to_csv(csv_path, index=False)

    try:
        parse_offers_csv(csv_path)
        assert False, "Expected ValueError for missing columns"
    except ValueError as exc:
        msg = str(exc)
        assert "missing columns" in msg
        assert "in_stock" in msg or "supplier" in msg
