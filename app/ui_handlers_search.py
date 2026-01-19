"""Search handler business logic - separated from Gradio UI concerns."""

from __future__ import annotations

from typing import Any

from .api_client import api_post_silent
from .logging_utils import log_exception
from .search import search
from .types import Brake, Freehub, Rotor, SearchRequest
from .ui_helpers import active_filters_list, annotate_low_coverage, calculate_coverage
from .ui_models import BudgetUpdate, FacetUpdate, SearchHandlerResult


def _do_search(
    query: str,
    speed: str,
    freehub: str,
    brake: str,
    axle: str,
    rotor: str,
    budget: float | None,
    category: str | None,
    suppliers_sel: list[str] | None,
    in_stock_only: bool | None,
) -> tuple[list[tuple[Any, ...]], list[tuple[str, str]], dict[str, str], str]:
    """
    Execute search and return results.

    This is the core search function that interfaces with the search module.

    Args:
        query: Search query text
        speed: Speed filter (e.g., "11-speed")
        freehub: Freehub filter (e.g., "Shimano")
        brake: Brake type filter (e.g., "Disc")
        axle: Axle type filter (e.g., "Thru-axle")
        rotor: Rotor size filter (e.g., "160mm")
        budget: Budget limit (None means no limit)
        category: Category filter (e.g., "MTB")
        suppliers_sel: List of selected supplier names
        in_stock_only: Whether to filter for in-stock items only

    Returns:
        Tuple of (rows, options, mapping, message)
    """
    # Create search request
    req = SearchRequest(
        query_text=(query or None),
        speed=(speed or None),
        freehub=(Freehub(freehub) if freehub else None),
        brake=(Brake(brake) if brake else None),
        axle=(axle or None),
        rotor=(Rotor(rotor) if rotor else None),
        budget_max=budget,
        category=(category or None),
        suppliers=(suppliers_sel or []),
        in_stock_only=bool(in_stock_only),
    )

    # Execute search
    res = search(req)

    # Build rows for DataFrame
    rows = [
        (
            item.brand,
            item.mpn,
            item.supplier,
            f"€{item.price:.2f}",
            "Sì" if item.in_stock else "No",
        )
        for item in res.items
    ]

    # Build options for dropdown (label, value)
    options = [
        (f"€{item.price:.2f} - {item.supplier}", str(item.id)) for item in res.items
    ]

    # Build mapping from offer ID to PN
    mapping = {str(item.id): item.mpn for item in res.items}

    msg = f"Trovati {len(res.items)} risultati"

    return rows, options, mapping, msg


def handle_search_request(
    query: str,
    speed: str,
    freehub: str,
    brake: str,
    axle: str,
    rotor: str,
    budget: str | None,
    category: str | None,
    suppliers_sel: list[str] | None,
    in_stock_only: bool,
) -> SearchHandlerResult:
    """
    Handle search request and return structured result.

    This is the main business logic function that:
    1. Executes the search via _do_search()
    2. Fetches facets from API
    3. Processes facets and builds UI state
    4. Returns SearchHandlerResult with all data

    The Gradio wrapper in ui.py converts this result to gr.update() calls.

    Args:
        query: Search query text
        speed: Speed filter value
        freehub: Freehub filter value
        brake: Brake filter value
        axle: Axle filter value
        rotor: Rotor filter value
        budget: Budget limit as string (empty string means no limit)
        category: Category filter value
        suppliers_sel: List of selected suppliers
        in_stock_only: Whether to filter for in-stock only

    Returns:
        SearchHandlerResult with all search results and facet updates
    """
    # Convert budget to float for search
    budget_float = None
    if budget is not None and budget != "":
        try:
            bval = float(budget)
            if bval > 0:
                budget_float = bval
        except ValueError:
            pass

    # Execute core search
    rows, options, mapping, msg = _do_search(
        query,
        speed,
        freehub,
        brake,
        axle,
        rotor,
        budget_float,
        category,
        suppliers_sel,
        in_stock_only,
    )

    # Process options for UI
    labels = [opt[0] for opt in options]
    default_label = labels[0] if labels else None

    # Fetch facets from API to refresh filter options/info
    try:
        payload = {
            "query_text": query or None,
            "speed": speed or None,
            "freehub": freehub or None,
            "brake": brake or None,
            "axle": axle or None,
            "rotor": rotor or None,
            "budget_max": budget_float,
            "category": category or None,
            "suppliers": suppliers_sel or [],
            "in_stock_only": bool(in_stock_only),
        }
        r = api_post_silent("/facets", payload, timeout=10)

        if r.status_code == 200:
            f = r.json()

            # Build info strings with counts
            speed_info = ", ".join(
                [f"{k} ({v})" for k, v in sorted(f.get("speed", {}).items())]
            )
            freehub_info = ", ".join(
                [f"{k} ({v})" for k, v in sorted(f.get("freehub", {}).items())]
            )
            brake_info = ", ".join(
                [f"{k} ({v})" for k, v in sorted(f.get("brake", {}).items())]
            )
            axle_info = ", ".join(
                [f"{k} ({v})" for k, v in sorted(f.get("axle", {}).items())]
            )
            rotor_info = ", ".join(
                [f"{k} ({v})" for k, v in sorted(f.get("rotor", {}).items())]
            )

            # Extract choices (only keys with count>0)
            speed_choices = sorted(list(f.get("speed", {}).keys()))
            freehub_choices = sorted(list(f.get("freehub", {}).keys()))
            brake_choices = sorted(list(f.get("brake", {}).keys()))
            rotor_choices = sorted(list(f.get("rotor", {}).keys()))
            axle_choices = sorted(list(f.get("axle", {}).keys()))
            category_choices = sorted(list(f.get("category", {}).keys()))

            # Calculate coverage for interactivity gating
            totals = f.get("totals", {})
            prod_total = int(totals.get("products", 0) or 0) or 1

            cov_speed = calculate_coverage(f.get("speed", {}), prod_total)
            cov_freehub = calculate_coverage(f.get("freehub", {}), prod_total)
            cov_brake = calculate_coverage(f.get("brake", {}), prod_total)
            cov_rotor = calculate_coverage(f.get("rotor", {}), prod_total)

            # Reset value to "" if current selection disappears from choices
            speed_val = speed if speed in speed_choices else ""
            freehub_val = freehub if freehub in freehub_choices else ""
            brake_val = brake if brake in brake_choices else ""
            rotor_val = rotor if rotor in rotor_choices else ""
            category_val = category if category in category_choices else ""

            # Build facet updates
            speed_update = FacetUpdate(
                choices=[""] + speed_choices,
                value=speed_val,
                info=annotate_low_coverage(speed_info or None, cov_speed),
                interactive=(cov_speed >= 0.15),
                coverage=cov_speed,
            )

            freehub_update = FacetUpdate(
                choices=[""] + freehub_choices,
                value=freehub_val,
                info=annotate_low_coverage(freehub_info or None, cov_freehub),
                interactive=(cov_freehub >= 0.15),
                coverage=cov_freehub,
            )

            brake_update = FacetUpdate(
                choices=[""] + brake_choices,
                value=brake_val,
                info=annotate_low_coverage(brake_info or None, cov_brake),
                interactive=(cov_brake >= 0.15),
                coverage=cov_brake,
            )

            rotor_update = FacetUpdate(
                choices=[""] + rotor_choices,
                value=rotor_val,
                info=annotate_low_coverage(rotor_info or None, cov_rotor),
                interactive=(cov_rotor >= 0.15),
                coverage=cov_rotor,
            )

            axle_update = FacetUpdate(
                choices=axle_choices,
                value=None,
                info=axle_info or None,
                interactive=(cov_speed >= 0.15),  # Axle uses speed coverage
            )

            # Category update
            category_info = (
                None if category_choices else "Nessuna categoria nei risultati"
            )
            category_update = FacetUpdate(
                choices=[""] + category_choices,
                value=category_val,
                info=category_info,
                interactive=bool(category_choices),
            )

            # Budget update
            price = f.get("price", {})
            price_info = None
            if price and price.get("max") is not None and price.get("min") is not None:
                price_info = f"Prezzo min/max: €{float(price['min']):.2f} – €{float(price['max']):.2f}"

            max_val = float(price.get("max") or 0.0)
            # If budget is None or 0, keep slider at 0; else clamp in [min,max]
            if budget is None or budget == "" or float(budget or 0) <= 0:
                slider_val = 0
            else:
                slider_val = max(min(int(float(budget)), int(max_val)), 0)

            budget_update = BudgetUpdate(
                info=price_info,
                slider_min=0,
                slider_max=max(100, int(max_val) or 100),
                slider_value=slider_val,
            )

            # Suppliers choices
            suppliers_choices = sorted(list(f.get("supplier", {}).keys()))

        else:
            # API error - return empty facets
            speed_update = FacetUpdate(
                choices=[], value=None, info=None, interactive=False
            )
            freehub_update = FacetUpdate(
                choices=[], value=None, info=None, interactive=False
            )
            brake_update = FacetUpdate(
                choices=[], value=None, info=None, interactive=False
            )
            rotor_update = FacetUpdate(
                choices=[], value=None, info=None, interactive=False
            )
            axle_update = FacetUpdate(
                choices=[], value=None, info=None, interactive=False
            )
            category_update = FacetUpdate(
                choices=[], value=None, info=None, interactive=False
            )
            budget_update = BudgetUpdate(
                info=None, slider_min=0, slider_max=100, slider_value=0
            )
            suppliers_choices = []

    except Exception as exc:
        log_exception("ui", "facets", "failed to build facets", exc)
        # Exception - return empty facets
        speed_update = FacetUpdate(choices=[], value=None, info=None, interactive=False)
        freehub_update = FacetUpdate(
            choices=[], value=None, info=None, interactive=False
        )
        brake_update = FacetUpdate(choices=[], value=None, info=None, interactive=False)
        rotor_update = FacetUpdate(choices=[], value=None, info=None, interactive=False)
        axle_update = FacetUpdate(choices=[], value=None, info=None, interactive=False)
        category_update = FacetUpdate(
            choices=[], value=None, info=None, interactive=False
        )
        budget_update = BudgetUpdate(
            info=None, slider_min=0, slider_max=100, slider_value=0
        )
        suppliers_choices = []

    # Calculate active filters
    af = active_filters_list(
        category,
        suppliers_sel,
        in_stock_only,
        speed,
        freehub,
        brake,
        axle,
        rotor,
        budget,
    )

    return SearchHandlerResult(
        rows=rows,
        offer_labels=labels,
        default_label=default_label,
        mapping=mapping,
        message=msg,
        speed=speed_update,
        freehub=freehub_update,
        brake=brake_update,
        rotor=rotor_update,
        axle=axle_update,
        suppliers_choices=suppliers_choices,
        category=category_update,
        budget=budget_update,
        active_filters=af,
    )
