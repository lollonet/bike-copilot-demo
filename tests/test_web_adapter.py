from pathlib import Path

import pytest

from app.adapters.web_adapter import (
    parse_file,
    parse_detail_html,
    parse_html,
    build_search_urls,
    fetch_and_parse_urls,
    parse_sitemap_urls,
    _load_mapping,
)


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


def test_build_search_urls_encodes_query(tmp_path: Path) -> None:
    """build_search_urls should format and URL-encode the query."""
    mapping_yaml = tmp_path / "web.yaml"
    mapping_yaml.write_text(
        "\n".join(
            [
                "supplier: DemoWeb",
                "root: .item",
                "brand: .brand",
                "mpn: .mpn",
                "name: .name",
                "price: .price",
                "search:",
                "  url_template: 'https://shop.example/search?q={q}'",
            ]
        ),
        encoding="utf-8",
    )
    urls = build_search_urls("catena 11v HG", mapping_yaml)
    assert urls == ["https://shop.example/search?q=catena+11v+HG"]


def test_build_search_urls_missing_template_raises(tmp_path: Path) -> None:
    """Missing search/url_template should raise ValueError."""
    mapping_yaml = tmp_path / "web_missing.yaml"
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
    with pytest.raises(ValueError):
        build_search_urls("foo", mapping_yaml)


def test_fetch_and_parse_urls_with_pagination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """fetch_and_parse_urls should follow relative next links and aggregate offers."""
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
                "pagination:",
                "  next: 'a.next'",
            ]
        ),
        encoding="utf-8",
    )

    seed_html = """
    <html><body>
      <div class="item">
        <span class="brand">Shimano</span>
        <span class="mpn">C1</span>
        <span class="name">Catena 11v</span>
        <span class="price">10,50 €</span>
      </div>
      <a class="next" href="/page2">next</a>
    </body></html>
    """
    page2_html = """
    <html><body>
      <div class="item">
        <span class="brand">SRAM</span>
        <span class="mpn">PG-1230</span>
        <span class="name">Cassetta 12v</span>
        <span class="price">89,00 €</span>
      </div>
    </body></html>
    """

    mapping_html: dict[str, str] = {
        "https://shop.example/seed": seed_html,
        "https://shop.example/page2": page2_html,
    }

    import httpx
    import time

    class DummyResp:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(
            self,
            timeout: float,
            headers: dict[str, str],
            follow_redirects: bool,
            verify: bool,
        ):
            self._timeout = timeout
            self._headers = headers
            self._follow = follow_redirects
            self._verify = verify

        def get(self, url: str) -> DummyResp:
            html = mapping_html.get(url)
            if html is None:
                raise RuntimeError(f"Unexpected URL {url}")
            return DummyResp(html)

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(httpx, "Client", DummyClient, raising=False)
    monkeypatch.setattr(time, "sleep", lambda _s: None, raising=False)

    products, offers = fetch_and_parse_urls(
        ["https://shop.example/seed"],
        mapping_yaml,
        follow_next=True,
        max_pages=3,
        delay_sec=0.0,
    )
    # We expect two products and two offers from seed + page2
    assert len(products) == 2
    assert len(offers) == 2
    brands = {p.brand for p in products}
    assert {"Shimano", "SRAM"}.issubset(brands)


def test_fetch_and_parse_urls_query_pagination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Query-based pagination should append skip=N results until empty."""
    mapping_yaml = tmp_path / "web_query.yaml"
    mapping_yaml.write_text(
        "\n".join(
            [
                "supplier: DemoWeb",
                "root: .item",
                "brand: .brand",
                "mpn: .mpn",
                "name: .name",
                "price: .price",
                "pagination:",
                "  mode: query",
                "  param: skip",
                "  limit_selector: '#pagination'",
                "  limit: 1",
            ]
        ),
        encoding="utf-8",
    )

    first_page = """
    <html><body>
      <div id="pagination" style="display:none">1</div>
      <div class="item">
        <span class="brand">Shimano</span>
        <span class="mpn">C1</span>
        <span class="name">Catena 11v</span>
        <span class="price">10,50 €</span>
      </div>
    </body></html>
    """
    second_page = """
    <html><body>
      <div id="pagination" style="display:none">1</div>
      <div class="item">
        <span class="brand">SRAM</span>
        <span class="mpn">PG-1230</span>
        <span class="name">Cassetta 12v</span>
        <span class="price">89,00 €</span>
      </div>
    </body></html>
    """

    mapping_html: dict[str, str] = {
        "https://shop.example/list?publicPrices=true": first_page,
        "https://shop.example/list?publicPrices=true&skip=1": second_page,
    }

    import httpx
    import time

    class DummyResp:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(
            self,
            timeout: float,
            headers: dict[str, str],
            follow_redirects: bool,
            verify: bool,
        ):
            self._timeout = timeout
            self._headers = headers
            self._follow = follow_redirects
            self._verify = verify

        def get(self, url: str) -> DummyResp:
            html = mapping_html.get(url)
            if html is None:
                raise RuntimeError(f"Unexpected URL {url}")
            return DummyResp(html)

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(httpx, "Client", DummyClient, raising=False)
    monkeypatch.setattr(time, "sleep", lambda _s: None, raising=False)

    products, offers = fetch_and_parse_urls(
        ["https://shop.example/list?publicPrices=true"],
        mapping_yaml,
        follow_next=True,
        max_pages=2,
        delay_sec=0.0,
    )
    assert len(products) == 2
    assert len(offers) == 2
    brands = {p.brand for p in products}
    assert {"Shimano", "SRAM"}.issubset(brands)


def test_parse_sitemap_urls_index_and_urlset(monkeypatch: pytest.MonkeyPatch) -> None:
    """parse_sitemap_urls should handle sitemapindex and nested urlset."""
    index_xml = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap>
        <loc>https://example.com/sitemap1.xml</loc>
      </sitemap>
    </sitemapindex>
    """
    urlset_xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/page1</loc></url>
      <url><loc>https://example.com/page2</loc></url>
    </urlset>
    """

    import httpx

    mapping_xml: dict[str, str] = {
        "https://example.com/sitemap.xml": index_xml,
        "https://example.com/sitemap1.xml": urlset_xml,
    }

    class DummyResp:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(
            self,
            timeout: float,
            headers: dict[str, str],
            follow_redirects: bool,
            verify: bool,
        ):
            self._timeout = timeout
            self._headers = headers
            self._follow = follow_redirects
            self._verify = verify

        def get(self, url: str) -> DummyResp:
            xml = mapping_xml.get(url)
            if xml is None:
                raise RuntimeError(f"Unexpected URL {url}")
            return DummyResp(xml)

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(httpx, "Client", DummyClient, raising=False)

    urls = parse_sitemap_urls("https://example.com/sitemap.xml", limit=None)
    assert urls == ["https://example.com/page1", "https://example.com/page2"]

    # Limit should truncate the list.
    urls_limited = parse_sitemap_urls("https://example.com/sitemap.xml", limit=1)
    assert urls_limited == ["https://example.com/page1"]


def test_ciclopromo_listing_basic(tmp_path: Path) -> None:
    """Ensure CicloPromo listing mapping extracts at least one product/offer."""
    # Use the committed fixture file for reproducible testing
    html_path = Path("providers/html/ciclopromo-fixture.html")
    mapping_yaml = Path("providers/web-ciclopromo.yaml")

    # Skip test if mapping doesn't exist (not all environments have it)
    if not mapping_yaml.is_file():
        pytest.skip(f"Mapping file {mapping_yaml} not found")

    # Ensure fixture exists
    assert html_path.is_file(), f"Test fixture {html_path} not found"

    mp = _load_mapping(mapping_yaml)
    html = html_path.read_text(encoding="utf-8")
    products, offers = parse_html(html, mp)

    # Basic validation that parser works with the mapping
    assert products, "No products extracted from CicloPromo fixture"
    assert offers, "No offers extracted from CicloPromo fixture"
    assert all(o.supplier == "CicloPromo" for o in offers), (
        "Supplier mismatch in offers"
    )
