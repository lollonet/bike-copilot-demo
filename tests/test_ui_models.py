"""Unit tests for app.ui_models module."""

from __future__ import annotations

from app.ui_models import BudgetUpdate, FacetUpdate, SearchHandlerResult


def test_facet_update_creation() -> None:
    """Test FacetUpdate dataclass creation."""
    facet = FacetUpdate(
        choices=["11-speed", "12-speed"],
        value="11-speed",
        info="11-speed (42), 12-speed (18)",
        interactive=True,
        coverage=0.85,
    )

    assert facet.choices == ["11-speed", "12-speed"]
    assert facet.value == "11-speed"
    assert facet.info == "11-speed (42), 12-speed (18)"
    assert facet.interactive is True
    assert facet.coverage == 0.85


def test_facet_update_none_value() -> None:
    """Test FacetUpdate with None value (reset state)."""
    facet = FacetUpdate(
        choices=["Shimano", "SRAM"],
        value=None,
        info="Shimano (30), SRAM (15)",
        interactive=True,
        coverage=0.75,
    )

    assert facet.value is None
    assert facet.choices == ["Shimano", "SRAM"]


def test_facet_update_none_coverage() -> None:
    """Test FacetUpdate with default None coverage."""
    facet = FacetUpdate(
        choices=["option1"],
        value="option1",
        info="info",
        interactive=False,
    )

    assert facet.coverage is None


def test_facet_update_low_coverage() -> None:
    """Test FacetUpdate with low coverage (non-interactive)."""
    facet = FacetUpdate(
        choices=["rare-option"],
        value=None,
        info="rare-option (2)",
        interactive=False,
        coverage=0.05,
    )

    assert facet.interactive is False
    assert facet.coverage == 0.05


def test_budget_update_creation() -> None:
    """Test BudgetUpdate dataclass creation."""
    budget = BudgetUpdate(
        info="Prezzo min/max: €10.00 – €150.00",
        slider_min=0,
        slider_max=150,
        slider_value=100,
    )

    assert budget.info == "Prezzo min/max: €10.00 – €150.00"
    assert budget.slider_min == 0
    assert budget.slider_max == 150
    assert budget.slider_value == 100


def test_budget_update_none_info() -> None:
    """Test BudgetUpdate with None info (no price data)."""
    budget = BudgetUpdate(
        info=None,
        slider_min=0,
        slider_max=100,
        slider_value=0,
    )

    assert budget.info is None
    assert budget.slider_value == 0


def test_budget_update_no_limit() -> None:
    """Test BudgetUpdate with slider at 0 (no limit)."""
    budget = BudgetUpdate(
        info="Prezzo min/max: €5.00 – €200.00",
        slider_min=0,
        slider_max=200,
        slider_value=0,
    )

    assert budget.slider_value == 0


def test_search_handler_result_creation() -> None:
    """Test SearchHandlerResult dataclass creation."""
    result = SearchHandlerResult(
        rows=[("Brand", "PN123", "Product Name", "€50.00", "Dealer1", "Yes")],
        offer_labels=["€50.00 - Dealer1"],
        default_label="€50.00 - Dealer1",
        mapping={"offer_123": "PN123"},
        message="Found 1 product",
        speed=FacetUpdate(
            choices=["11-speed"],
            value="11-speed",
            info="11-speed (1)",
            interactive=True,
            coverage=1.0,
        ),
        freehub=FacetUpdate(
            choices=["Shimano"],
            value=None,
            info="Shimano (1)",
            interactive=True,
            coverage=1.0,
        ),
        brake=FacetUpdate(
            choices=["Disc"],
            value=None,
            info="Disc (1)",
            interactive=True,
            coverage=1.0,
        ),
        rotor=FacetUpdate(
            choices=["160mm"],
            value=None,
            info="160mm (1)",
            interactive=True,
            coverage=1.0,
        ),
        axle=FacetUpdate(
            choices=["Thru-axle"],
            value=None,
            info="Thru-axle (1)",
            interactive=True,
            coverage=1.0,
        ),
        suppliers_choices=["Dealer1"],
        category=FacetUpdate(
            choices=["MTB"],
            value="MTB",
            info=None,
            interactive=True,
            coverage=1.0,
        ),
        budget=BudgetUpdate(
            info="Prezzo min/max: €50.00 – €50.00",
            slider_min=0,
            slider_max=50,
            slider_value=0,
        ),
        active_filters=["category:MTB", "speed:11-speed"],
    )

    assert len(result.rows) == 1
    assert result.offer_labels == ["€50.00 - Dealer1"]
    assert result.default_label == "€50.00 - Dealer1"
    assert result.mapping == {"offer_123": "PN123"}
    assert result.message == "Found 1 product"
    assert result.speed.value == "11-speed"
    assert result.freehub.value is None
    assert result.suppliers_choices == ["Dealer1"]
    assert result.category.value == "MTB"
    assert result.budget.slider_value == 0
    assert len(result.active_filters) == 2


def test_search_handler_result_empty_results() -> None:
    """Test SearchHandlerResult with no search results."""
    result = SearchHandlerResult(
        rows=[],
        offer_labels=[],
        default_label=None,
        mapping={},
        message="No products found",
        speed=FacetUpdate(choices=[], value=None, info=None, interactive=False),
        freehub=FacetUpdate(choices=[], value=None, info=None, interactive=False),
        brake=FacetUpdate(choices=[], value=None, info=None, interactive=False),
        rotor=FacetUpdate(choices=[], value=None, info=None, interactive=False),
        axle=FacetUpdate(choices=[], value=None, info=None, interactive=False),
        suppliers_choices=[],
        category=FacetUpdate(
            choices=[],
            value=None,
            info="Nessuna categoria nei risultati",
            interactive=False,
        ),
        budget=BudgetUpdate(info=None, slider_min=0, slider_max=100, slider_value=0),
        active_filters=[],
    )

    assert result.rows == []
    assert result.default_label is None
    assert result.message == "No products found"
    assert result.speed.interactive is False
    assert result.category.info == "Nessuna categoria nei risultati"
    assert result.active_filters == []


def test_search_handler_result_with_filters() -> None:
    """Test SearchHandlerResult with multiple active filters."""
    result = SearchHandlerResult(
        rows=[("Brand", "PN", "Name", "€100", "Dealer", "Yes")],
        offer_labels=["€100 - Dealer"],
        default_label="€100 - Dealer",
        mapping={"1": "PN"},
        message="1 product",
        speed=FacetUpdate(choices=["12"], value="12", info="12 (1)", interactive=True),
        freehub=FacetUpdate(
            choices=["SRAM"], value="SRAM", info="SRAM (1)", interactive=True
        ),
        brake=FacetUpdate(
            choices=["Rim"], value="Rim", info="Rim (1)", interactive=True
        ),
        rotor=FacetUpdate(choices=[], value=None, info=None, interactive=False),
        axle=FacetUpdate(choices=["QR"], value="QR", info="QR (1)", interactive=True),
        suppliers_choices=["Dealer"],
        category=FacetUpdate(
            choices=["Road"], value="Road", info=None, interactive=True
        ),
        budget=BudgetUpdate(
            info="€100 – €100", slider_min=0, slider_max=100, slider_value=50
        ),
        active_filters=[
            "category:Road",
            "speed:12",
            "freehub:SRAM",
            "brake:Rim",
            "axle:QR",
            "budget:<= 50",
        ],
    )

    assert len(result.active_filters) == 6
    assert "category:Road" in result.active_filters
    assert "budget:<= 50" in result.active_filters
    assert result.budget.slider_value == 50


def test_search_handler_result_reset_values() -> None:
    """Test SearchHandlerResult with reset facet values (no longer available)."""
    result = SearchHandlerResult(
        rows=[("Brand", "PN", "Name", "€50", "Dealer", "Yes")],
        offer_labels=["€50 - Dealer"],
        default_label="€50 - Dealer",
        mapping={"1": "PN"},
        message="1 product",
        speed=FacetUpdate(
            choices=["11-speed", "12-speed"],
            value="",  # Reset because previous selection not available
            info="11-speed (1)",
            interactive=True,
            coverage=0.5,
        ),
        freehub=FacetUpdate(
            choices=["Shimano"],
            value="",  # Reset
            info="Shimano (1)",
            interactive=True,
            coverage=1.0,
        ),
        brake=FacetUpdate(
            choices=["Disc"], value="", info="Disc (1)", interactive=True
        ),
        rotor=FacetUpdate(choices=[], value="", info=None, interactive=False),
        axle=FacetUpdate(choices=[], value="", info=None, interactive=False),
        suppliers_choices=["Dealer"],
        category=FacetUpdate(
            choices=["MTB"], value="", info=None, interactive=True, coverage=1.0
        ),
        budget=BudgetUpdate(info="€50", slider_min=0, slider_max=50, slider_value=0),
        active_filters=[],
    )

    # Empty string means value was reset
    assert result.speed.value == ""
    assert result.freehub.value == ""
    assert result.category.value == ""
