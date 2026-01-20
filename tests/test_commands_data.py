"""Tests for data CLI commands and helpers."""

from __future__ import annotations


def test_escape_md():
    """Test markdown pipe escaping."""
    from app.cli_helpers.data_helpers import escape_md

    assert escape_md("hello") == "hello"
    assert escape_md("test|pipe") == "test\\|pipe"
    assert escape_md("multi|ple|pipes") == "multi\\|ple\\|pipes"
    assert escape_md("") == ""


def test_export_row_model():
    """Test ExportRow model creation."""
    from app.cli_helpers.data_helpers import ExportRow

    row = ExportRow(
        brand="Shimano",
        mpn="CS-M7100",
        name="Cassette",
        category="Drivetrain",
        supplier="TestSupplier",
        price=89.99,
        in_stock=True,
        lead_time_days=2,
    )

    assert row.brand == "Shimano"
    assert row.mpn == "CS-M7100"
    assert row.name == "Cassette"
    assert row.category == "Drivetrain"
    assert row.supplier == "TestSupplier"
    assert row.price == 89.99
    assert row.in_stock is True
    assert row.lead_time_days == 2


def test_export_row_optional_fields():
    """Test ExportRow with optional fields."""
    from app.cli_helpers.data_helpers import ExportRow

    row = ExportRow(
        brand="SRAM",
        mpn="PG-1230",
        name="Cassette",
        supplier="TestSupplier",
        price=120.00,
        in_stock=False,
    )

    assert row.category is None
    assert row.lead_time_days is None


def test_render_export_table_empty():
    """Test rendering empty export table."""
    from app.cli_helpers.data_helpers import render_export_table

    result = render_export_table([])
    lines = result.split("\n")

    # Should have header and separator
    assert len(lines) == 2
    assert "brand" in lines[0]
    assert "mpn" in lines[0]
    assert lines[1].startswith("|---|")


def test_render_export_table_with_data():
    """Test rendering export table with data."""
    from app.cli_helpers.data_helpers import ExportRow, render_export_table

    items = [
        ExportRow(
            brand="Shimano",
            mpn="CS-M7100",
            name="Cassette",
            category="Drivetrain",
            supplier="Dealer1",
            price=89.99,
            in_stock=True,
            lead_time_days=2,
        ),
        ExportRow(
            brand="SRAM",
            mpn="PG-1230",
            name="Cassette 12sp",
            supplier="Dealer2",
            price=120.50,
            in_stock=False,
        ),
    ]

    result = render_export_table(items)
    lines = result.split("\n")

    # Header + separator + 2 data rows
    assert len(lines) == 4
    assert "Shimano" in lines[2]
    assert "CS-M7100" in lines[2]
    assert "89.99" in lines[2]
    assert "yes" in lines[2]
    assert "SRAM" in lines[3]
    assert "120.50" in lines[3]
    assert "no" in lines[3]


def test_render_export_table_escapes_pipes():
    """Test that render_export_table escapes pipe characters."""
    from app.cli_helpers.data_helpers import ExportRow, render_export_table

    items = [
        ExportRow(
            brand="Test|Brand",
            mpn="MPN|123",
            name="Name|With|Pipes",
            supplier="Supplier1",
            price=50.00,
            in_stock=True,
        )
    ]

    result = render_export_table(items)

    # Should escape pipes in data
    assert "Test\\|Brand" in result
    assert "MPN\\|123" in result
    assert "Name\\|With\\|Pipes" in result


def test_alias_entry_type():
    """Test AliasEntry TypedDict structure."""
    from app.cli_helpers.data_helpers import AliasEntry

    entry: AliasEntry = {
        "maker_pn": "CN-HG601",
        "dealer_pn": "ICNHG601116",
        "confidence": 0.98,
    }

    assert entry["maker_pn"] == "CN-HG601"
    assert entry["dealer_pn"] == "ICNHG601116"
    assert entry["confidence"] == 0.98


def test_alias_block_type():
    """Test AliasBlock TypedDict structure."""
    from app.cli_helpers.data_helpers import AliasBlock

    block: AliasBlock = {
        "dealer": "DealerA",
        "aliases": [
            {"maker_pn": "CN-HG601", "dealer_pn": "ICNHG601116", "confidence": 0.98}
        ],
    }

    assert block["dealer"] == "DealerA"
    assert len(block["aliases"]) == 1  # type: ignore


def test_dealer_from_block():
    """Test extracting dealer name from alias block."""
    from app.cli_helpers.data_helpers import dealer_from_block

    block = {"dealer": "DealerA", "aliases": []}
    assert dealer_from_block(block) == "DealerA"

    block_none = {"aliases": []}
    assert dealer_from_block(block_none) is None

    block_empty = {"dealer": "", "aliases": []}
    assert dealer_from_block(block_empty) is None

    block_whitespace = {"dealer": "  ", "aliases": []}
    assert dealer_from_block(block_whitespace) is None


def test_alias_confidence():
    """Test extracting confidence from alias entry."""
    from app.cli_helpers.data_helpers import alias_confidence

    entry_with_conf = {"maker_pn": "test", "confidence": 0.95}
    assert alias_confidence(entry_with_conf) == 0.95

    entry_without_conf = {"maker_pn": "test"}
    assert alias_confidence(entry_without_conf) == 1.0

    entry_zero_conf = {"maker_pn": "test", "confidence": 0.0}
    assert alias_confidence(entry_zero_conf) == 0.0


def test_normalized_alias_codes():
    """Test normalizing alias codes."""
    from app.cli_helpers.data_helpers import normalized_alias_codes

    # Mock normalize_pn function
    def mock_normalize(pn: str) -> str:
        return pn.upper().replace("-", "")

    entry = {"maker_pn": "cn-hg601", "dealer_pn": "icnhg601116"}
    maker, dealer = normalized_alias_codes(entry, mock_normalize)

    assert maker == "CNHG601"
    assert dealer == "ICNHG601116"


def test_normalized_alias_codes_empty_dealer():
    """Test normalizing alias codes with empty dealer PN."""
    from app.cli_helpers.data_helpers import normalized_alias_codes

    def mock_normalize(pn: str) -> str:
        return pn.upper()

    entry = {"maker_pn": "test"}
    maker, dealer = normalized_alias_codes(entry, mock_normalize)

    assert maker == "TEST"
    assert dealer is None


def test_build_export_rows():
    """Test building export rows from query results."""
    from app.cli_helpers.data_helpers import build_export_rows
    from app.models import SupplierOffer

    # Create mock query result tuple
    mock_offer = SupplierOffer()
    rows = [
        (
            mock_offer,
            "Dealer1",  # supplier
            89.99,  # price
            True,  # in_stock
            2,  # lead_time_days
            "Shimano",  # brand
            "CS-M7100",  # mpn
            "Cassette",  # name
            "Drivetrain",  # category
        )
    ]

    items = build_export_rows(rows)

    assert len(items) == 1
    assert items[0].brand == "Shimano"
    assert items[0].mpn == "CS-M7100"
    assert items[0].name == "Cassette"
    assert items[0].category == "Drivetrain"
    assert items[0].supplier == "Dealer1"
    assert items[0].price == 89.99
    assert items[0].in_stock is True
    assert items[0].lead_time_days == 2


def test_build_export_rows_none_values():
    """Test building export rows with None values."""
    from app.cli_helpers.data_helpers import build_export_rows
    from app.models import SupplierOffer

    mock_offer = SupplierOffer()
    rows = [
        (
            mock_offer,
            "Dealer1",
            100.0,
            False,
            None,  # lead_time_days is None
            "Brand",
            "MPN",
            "Name",
            None,  # category is None
        )
    ]

    items = build_export_rows(rows)

    assert len(items) == 1
    assert items[0].category is None
    assert items[0].lead_time_days is None
