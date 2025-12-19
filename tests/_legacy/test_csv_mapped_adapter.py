from __future__ import annotations

from pathlib import Path

from app.adapters.csv_mapped_adapter import parse_unified_csv


def test_parse_unified_csv_basic(tmp_path: Path) -> None:
    csv_path = tmp_path / "catalog.csv"
    mapping_path = tmp_path / "mapping.yaml"

    csv_path.write_text(
        "\n".join(
            [
                "brand;mpn;name;price;category;sku",
                "Shimano;CN-HG601;Catena 11v;24,90;Catene;ICNHG601116",
                "SRAM;PG-1230;Cassetta 12v;89.00;Cassetta;PG1230SKU",
            ]
        ),
        encoding="utf-8",
    )
    mapping_path.write_text(
        "\n".join(
            [
                "supplier: CatalogoMTB",
                "delimiter: ';'",
                "columns:",
                "  brand: brand",
                "  mpn: mpn",
                "  name: name",
                "  price: price",
                "  category: category",
                "  dealer_code: sku",
                "defaults:",
                "  in_stock: true",
                "  lead_time_days: 2",
            ]
        ),
        encoding="utf-8",
    )

    products, offers = parse_unified_csv(csv_path, mapping_path)
    assert len(products) == 2
    assert len(offers) == 2
    p0 = products[0]
    o0 = offers[0]
    assert p0.brand == "Shimano"
    assert p0.mpn == "CN-HG601"
    assert p0.category == "Catene"
    assert o0.supplier == "CatalogoMTB"
    assert abs(o0.price - 24.90) < 0.01
    assert o0.in_stock is True
    assert o0.lead_time_days == 2
    assert o0.extra.get("dealer_pn") == "ICNHG601116"
