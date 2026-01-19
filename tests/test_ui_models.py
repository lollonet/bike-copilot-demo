"""Tests for UI model dataclasses."""

from __future__ import annotations

from app.ui_models import BudgetUpdate, FacetUpdate, SearchHandlerResult


def test_facet_update_creation():
    """Test FacetUpdate dataclass instantiation."""
    facet = FacetUpdate(
        choices=["option1", "option2"],
        value="option1",
        info="Test info",
        interactive=True,
        coverage=0.85,
    )
    assert facet.choices == ["option1", "option2"]
    assert facet.value == "option1"
    assert facet.info == "Test info"
    assert facet.interactive is True
    assert facet.coverage == 0.85


def test_facet_update_with_none_values():
    """Test FacetUpdate with None values."""
    facet = FacetUpdate(
        choices=["option1"],
        value=None,
        info=None,
        interactive=False,
        coverage=None,
    )
    assert facet.value is None
    assert facet.info is None
    assert facet.interactive is False
    assert facet.coverage is None


def test_facet_update_low_coverage():
    """Test FacetUpdate with low coverage."""
    facet = FacetUpdate(
        choices=["rare_option"],
        value=None,
        info="Very few items",
        interactive=False,
        coverage=0.05,
    )
    assert facet.coverage == 0.05
    assert facet.interactive is False


def test_budget_update_creation():
    """Test BudgetUpdate dataclass instantiation."""
    budget = BudgetUpdate(
        info="Prezzo min/max: €10.00 – €100.00",
        slider_min=0,
        slider_max=100,
        slider_value=50,
    )
    assert budget.info == "Prezzo min/max: €10.00 – €100.00"
    assert budget.slider_min == 0
    assert budget.slider_max == 100
    assert budget.slider_value == 50


def test_budget_update_with_none_info():
    """Test BudgetUpdate with None info."""
    budget = BudgetUpdate(info=None, slider_min=0, slider_max=100, slider_value=0)
    assert budget.info is None
    assert budget.slider_value == 0


def test_budget_update_no_limit():
    """Test BudgetUpdate representing no budget limit (value=0)."""
    budget = BudgetUpdate(
        info="Prezzo min/max: €10.00 – €500.00",
        slider_min=0,
        slider_max=500,
        slider_value=0,
    )
    assert budget.slider_value == 0  # 0 means no budget limit


def test_search_handler_result_with_results():
    """Test SearchHandlerResult with actual search results."""
    result = SearchHandlerResult(
        rows=[[1, "Brand1", "PN123", "Supplier1", 50.0, "Sì", 5, 0.95]],
        offer_labels=["€50.00 - Supplier1"],
        default_label="€50.00 - Supplier1",
        mapping={
            1: {
                "brand": "Brand1",
                "mpn": "PN123",
                "supplier": "Supplier1",
                "price": 50.0,
            }
        },
        message="Trovate 1 offerte",
        speed=FacetUpdate(["", "11-speed"], None, "11-speed (1)", True, 1.0),
        freehub=FacetUpdate(["", "Shimano"], None, "Shimano (1)", True, 1.0),
        brake=FacetUpdate(["", "Centerlock"], None, "Centerlock (1)", True, 1.0),
        rotor=FacetUpdate(["", "160mm"], None, "160mm (1)", True, 1.0),
        axle=FacetUpdate([""], None, "Thru Axle (1)", True),
        suppliers_choices=["Supplier1"],
        category=FacetUpdate(["", "MTB"], None, None, True, 1.0),
        budget=BudgetUpdate("Prezzo min/max: €50.00 – €50.00", 0, 100, 0),
        active_filters=[],
    )
    assert len(result.rows) == 1
    assert result.default_label == "€50.00 - Supplier1"
    assert result.mapping[1]["mpn"] == "PN123"
    assert result.message == "Trovate 1 offerte"


def test_search_handler_result_empty():
    """Test SearchHandlerResult with no results."""
    result = SearchHandlerResult(
        rows=[],
        offer_labels=[],
        default_label=None,
        mapping={},
        message="Trovate 0 offerte",
        speed=FacetUpdate([""], None, None, False),
        freehub=FacetUpdate([""], None, None, False),
        brake=FacetUpdate([""], None, None, False),
        rotor=FacetUpdate([""], None, None, False),
        axle=FacetUpdate([""], None, None, False),
        suppliers_choices=[],
        category=FacetUpdate([""], None, "Nessuna categoria nei risultati", False),
        budget=BudgetUpdate(None, 0, 100, 0),
        active_filters=[],
    )
    assert len(result.rows) == 0
    assert result.default_label is None
    assert len(result.mapping) == 0


def test_search_handler_result_with_multiple_filters():
    """Test SearchHandlerResult with active filters."""
    result = SearchHandlerResult(
        rows=[[1, "Brand1", "PN123", "Supplier1", 50.0, "Sì", 5, 0.95]],
        offer_labels=["€50.00 - Supplier1"],
        default_label="€50.00 - Supplier1",
        mapping={
            1: {
                "brand": "Brand1",
                "mpn": "PN123",
                "supplier": "Supplier1",
                "price": 50.0,
            }
        },
        message="Trovate 1 offerte",
        speed=FacetUpdate(["", "11-speed"], "11-speed", "11-speed (1)", True, 1.0),
        freehub=FacetUpdate(["", "Shimano"], "Shimano", "Shimano (1)", True, 1.0),
        brake=FacetUpdate(["", "Centerlock"], None, "Centerlock (1)", True, 1.0),
        rotor=FacetUpdate(["", "160mm"], None, "160mm (1)", True, 1.0),
        axle=FacetUpdate(["", "Thru Axle"], None, "Thru Axle (1)", True),
        suppliers_choices=["Supplier1"],
        category=FacetUpdate(["", "MTB"], "MTB", None, True, 1.0),
        budget=BudgetUpdate("Prezzo min/max: €50.00 – €50.00", 0, 100, 50),
        active_filters=[
            "category:MTB",
            "speed:11-speed",
            "freehub:Shimano",
            "budget:<= 50",
        ],
    )
    assert len(result.active_filters) == 4
    assert "category:MTB" in result.active_filters


def test_search_handler_result_facet_value_reset():
    """Test SearchHandlerResult with facet value reset (not in choices)."""
    # User selected "12-speed" but only "11-speed" available in results
    result = SearchHandlerResult(
        rows=[[1, "Brand1", "PN123", "Supplier1", 50.0, "Sì", 5, 0.95]],
        offer_labels=["€50.00 - Supplier1"],
        default_label="€50.00 - Supplier1",
        mapping={
            1: {
                "brand": "Brand1",
                "mpn": "PN123",
                "supplier": "Supplier1",
                "price": 50.0,
            }
        },
        message="Trovate 1 offerte",
        speed=FacetUpdate(
            ["", "11-speed"], "", "11-speed (1)", True, 1.0
        ),  # Value reset to ""
        freehub=FacetUpdate(["", "Shimano"], None, "Shimano (1)", True, 1.0),
        brake=FacetUpdate(["", "Centerlock"], None, "Centerlock (1)", True, 1.0),
        rotor=FacetUpdate(["", "160mm"], None, "160mm (1)", True, 1.0),
        axle=FacetUpdate(["", "Thru Axle"], None, "Thru Axle (1)", True),
        suppliers_choices=["Supplier1"],
        category=FacetUpdate(["", "MTB"], None, None, True, 1.0),
        budget=BudgetUpdate("Prezzo min/max: €50.00 – €50.00", 0, 100, 0),
        active_filters=[],
    )
    assert result.speed.value == ""  # Value was reset because "12-speed" not in choices
    assert result.speed.choices == ["", "11-speed"]
