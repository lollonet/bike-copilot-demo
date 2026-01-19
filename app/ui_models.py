"""Data models for UI layer - type-safe result structures for handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FacetUpdate:
    """
    Single facet update data for UI components.

    Represents the state of a single facet filter (speed, freehub, brake, etc.)
    including available choices, current value, info text, and interactivity.

    Attributes:
        choices: List of available options for this facet
        value: Currently selected value (None if reset or no selection)
        info: Formatted info string with counts (e.g., "11-speed (42), 12-speed (18)")
        interactive: Whether the facet should be interactive (based on coverage threshold)
        coverage: Coverage ratio (0.0 to 1.0) of this facet vs total products
    """

    choices: list[str]
    value: str | None
    info: str | None
    interactive: bool
    coverage: float | None = None


@dataclass
class BudgetUpdate:
    """
    Budget filter update data for UI components.

    Represents both the budget number input and slider state.

    Attributes:
        info: Price range info string (e.g., "Prezzo min/max: €10.00 – €150.00")
        slider_min: Minimum value for budget slider
        slider_max: Maximum value for budget slider
        slider_value: Current slider value (0 means no limit)
    """

    info: str | None
    slider_min: int
    slider_max: int
    slider_value: int


@dataclass
class SearchHandlerResult:
    """
    Complete result from search handler business logic.

    This dataclass separates business logic concerns from Gradio UI concerns.
    The handler computes these values, and the Gradio wrapper converts them
    to gr.update() calls.

    Attributes:
        rows: Search result rows for DataFrame display
        offer_labels: Labels for offer selector dropdown (e.g., ["€20.00 - Dealer1"])
        default_label: Default selected label (first option)
        mapping: Offer ID to maker PN mapping (hidden state for cart operations)
        message: Status message to display to user

        speed: Speed facet update data
        freehub: Freehub facet update data
        brake: Brake facet update data
        rotor: Rotor size facet update data
        axle: Axle type facet update data

        suppliers_choices: Available supplier choices for multi-select dropdown
        category: Category facet update data
        budget: Budget filter update data

        active_filters: List of active filter strings for display chips
    """

    # Search results from _do_search
    rows: list[tuple[Any, ...]]
    offer_labels: list[str]
    default_label: str | None
    mapping: dict[str, str]
    message: str

    # Facet updates
    speed: FacetUpdate
    freehub: FacetUpdate
    brake: FacetUpdate
    rotor: FacetUpdate
    axle: FacetUpdate

    # Other filter updates
    suppliers_choices: list[str]
    category: FacetUpdate
    budget: BudgetUpdate

    # Active filters
    active_filters: list[str]
