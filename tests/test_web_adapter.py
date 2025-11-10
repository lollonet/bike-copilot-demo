from pathlib import Path

from app.adapters.web_adapter import parse_file


def test_parse_web_example(tmp_path: Path) -> None:
    html = Path("providers/html/example.html")
    mapping = Path("providers/web-example.yaml")
    products, offers = parse_file(html, mapping)
    assert len(products) == 2
    assert len(offers) == 2
    assert offers[0].brand == "Shimano"
    assert offers[0].price == 24.90
    assert offers[0].in_stock is True
