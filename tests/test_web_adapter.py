from pathlib import Path

from app.adapters.web_adapter import parse_file, parse_detail_html


def test_parse_web_example(tmp_path: Path) -> None:
    html = Path("providers/html/example.html")
    mapping = Path("providers/web-example.yaml")
    products, offers = parse_file(html, mapping)
    assert len(products) == 2
    assert len(offers) == 2
    assert offers[0].brand == "Shimano"
    assert offers[0].price == 24.90
    assert offers[0].in_stock is True


def test_woo_sale_price_parsing(tmp_path: Path) -> None:
    html = Path("providers/html/woo-sale.html")
    mapping = Path("providers/web-ciclimontanini.yaml")
    # Use detail parser to read current price from <ins>
    mapping_yaml = mapping
    from app.adapters.web_adapter import _load_mapping

    mp = _load_mapping(mapping_yaml)
    p, o = parse_detail_html(html.read_text(encoding="utf-8"), mp)
    assert p is not None and o is not None
    assert o.price == 9.90


def test_storeden_meta_and_breadcrumb(tmp_path: Path) -> None:
    html = Path("providers/html/storeden-product.html")
    from app.adapters.web_adapter import _load_mapping

    mp = _load_mapping(Path("providers/web-ciclodiffusione.yaml"))
    p, o = parse_detail_html(html.read_text(encoding="utf-8"), mp)
    assert p is not None and o is not None
    # OG meta contains price; breadcrumb contains category
    assert o.price == 56.00
    assert p.category is not None and len(p.category) > 0
