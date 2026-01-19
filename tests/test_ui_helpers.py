"""Unit tests for app.ui_helpers module."""

from __future__ import annotations

from app.ui_helpers import (
    active_filters_list,
    annotate_low_coverage,
    calculate_coverage,
)


def test_active_filters_list_empty() -> None:
    """Test active_filters_list with no filters selected."""
    result = active_filters_list(
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget=None,
    )
    assert result == []


def test_active_filters_list_category_only() -> None:
    """Test active_filters_list with only category selected."""
    result = active_filters_list(
        category="MTB",
        suppliers_sel=None,
        in_stock_only=False,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget=None,
    )
    assert result == ["category:MTB"]


def test_active_filters_list_suppliers() -> None:
    """Test active_filters_list with suppliers selected."""
    result = active_filters_list(
        category=None,
        suppliers_sel=["Ciclopromo", "Montanini"],
        in_stock_only=False,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget=None,
    )
    # Suppliers should be sorted
    assert result == ["suppliers:Ciclopromo,Montanini"]


def test_active_filters_list_in_stock() -> None:
    """Test active_filters_list with in_stock_only flag."""
    result = active_filters_list(
        category=None,
        suppliers_sel=None,
        in_stock_only=True,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget=None,
    )
    assert result == ["in_stock:true"]


def test_active_filters_list_technical_specs() -> None:
    """Test active_filters_list with technical specification filters."""
    result = active_filters_list(
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
        speed="11",
        freehub="Shimano",
        brake="Disc",
        axle="Thru-axle",
        rotor="160mm",
        budget=None,
    )
    assert result == [
        "speed:11",
        "freehub:Shimano",
        "brake:Disc",
        "axle:Thru-axle",
        "rotor:160mm",
    ]


def test_active_filters_list_budget_valid() -> None:
    """Test active_filters_list with valid budget."""
    result = active_filters_list(
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget="150.50",
    )
    assert result == ["budget:<= 150"]


def test_active_filters_list_budget_zero() -> None:
    """Test active_filters_list with zero budget (should be ignored)."""
    result = active_filters_list(
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget="0",
    )
    assert result == []


def test_active_filters_list_budget_invalid() -> None:
    """Test active_filters_list with invalid budget (should be ignored)."""
    result = active_filters_list(
        category=None,
        suppliers_sel=None,
        in_stock_only=False,
        speed=None,
        freehub=None,
        brake=None,
        axle=None,
        rotor=None,
        budget="invalid",
    )
    # Invalid budget should be logged and ignored
    assert result == []


def test_active_filters_list_all_filters() -> None:
    """Test active_filters_list with all filters combined."""
    result = active_filters_list(
        category="Road",
        suppliers_sel=["Dealer1", "Dealer2"],
        in_stock_only=True,
        speed="12",
        freehub="Campagnolo",
        brake="Rim",
        axle="Quick-release",
        rotor="140mm",
        budget="200",
    )
    assert len(result) == 9
    assert "category:Road" in result
    assert "suppliers:Dealer1,Dealer2" in result
    assert "in_stock:true" in result
    assert "speed:12" in result
    assert "freehub:Campagnolo" in result
    assert "brake:Rim" in result
    assert "axle:Quick-release" in result
    assert "rotor:140mm" in result
    assert "budget:<= 200" in result


def test_calculate_coverage_zero_total() -> None:
    """Test calculate_coverage with zero total products."""
    result = calculate_coverage({"option1": 5, "option2": 10}, 0)
    assert result == 0.0


def test_calculate_coverage_empty_counts() -> None:
    """Test calculate_coverage with empty counts dictionary."""
    result = calculate_coverage({}, 100)
    assert result == 0.0


def test_calculate_coverage_none_counts() -> None:
    """Test calculate_coverage with None counts."""
    result = calculate_coverage(None, 100)  # type: ignore[arg-type]
    assert result == 0.0


def test_calculate_coverage_partial() -> None:
    """Test calculate_coverage with partial coverage."""
    counts = {"11-speed": 30, "12-speed": 20}
    total = 100
    result = calculate_coverage(counts, total)
    assert result == 0.5  # 50 / 100


def test_calculate_coverage_full() -> None:
    """Test calculate_coverage with full coverage."""
    counts = {"option1": 60, "option2": 40}
    total = 100
    result = calculate_coverage(counts, total)
    assert result == 1.0  # 100 / 100


def test_annotate_low_coverage_none_info() -> None:
    """Test annotate_low_coverage with None info."""
    result = annotate_low_coverage(None, 0.1)
    assert result is None


def test_annotate_low_coverage_below_threshold() -> None:
    """Test annotate_low_coverage with coverage below threshold."""
    result = annotate_low_coverage("Velocità", 0.1, threshold=0.15)
    assert result == "Velocità — poche specifiche nei risultati"


def test_annotate_low_coverage_at_threshold() -> None:
    """Test annotate_low_coverage with coverage at threshold."""
    result = annotate_low_coverage("Velocità", 0.15, threshold=0.15)
    assert result == "Velocità"


def test_annotate_low_coverage_above_threshold() -> None:
    """Test annotate_low_coverage with coverage above threshold."""
    result = annotate_low_coverage("Velocità", 0.5, threshold=0.15)
    assert result == "Velocità"


def test_annotate_low_coverage_custom_threshold() -> None:
    """Test annotate_low_coverage with custom threshold."""
    result = annotate_low_coverage("Freno", 0.25, threshold=0.3)
    assert result == "Freno — poche specifiche nei risultati"

    result = annotate_low_coverage("Freno", 0.35, threshold=0.3)
    assert result == "Freno"
