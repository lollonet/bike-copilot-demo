"""Type-safe dataclass models for UI handler results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FacetUpdate:
    """Single facet update data for UI components."""

    choices: list[str]
    value: str | None
    info: str | None
    interactive: bool
    coverage: float | None = None


@dataclass
class BudgetUpdate:
    """Budget filter update data for UI components."""

    info: str | None
    slider_min: int
    slider_max: int
    slider_value: int


@dataclass
class SearchHandlerResult:
    """Complete result from search handler business logic."""

    rows: list[list[object]]
    offer_labels: list[str]
    default_label: str | None
    mapping: dict[int, dict[str, Any]]
    message: str
    speed: FacetUpdate
    freehub: FacetUpdate
    brake: FacetUpdate
    rotor: FacetUpdate
    axle: FacetUpdate
    suppliers_choices: list[str]
    category: FacetUpdate
    budget: BudgetUpdate
    active_filters: list[str]
