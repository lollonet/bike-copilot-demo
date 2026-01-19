"""Business logic for search UI handler - separated from Gradio UI concerns."""

from __future__ import annotations

from typing import Any

from .api_client import api_post_silent
from .logging_utils import log_exception
from .search import search
from .types import Brake, Freehub, Rotor, SearchRequest
from .ui_helpers import active_filters_list, annotate_low_coverage, calculate_coverage
from .ui_models import BudgetUpdate, FacetUpdate, SearchHandlerResult

# Minimum coverage ratio required to enable facet interaction
# Facets with coverage below this threshold are disabled to prevent misleading filters
FACET_COVERAGE_THRESHOLD = 0.15


def _parse_budget(budget: str | None) -> float | None:
    """Parse budget string to float, returning None if invalid or non-positive."""
    if budget is None or budget == "":
        return None
    try:
        val = float(budget)
        return val if val > 0 else None
    except ValueError:
        return None


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
) -> tuple[list[list[object]], list[tuple[str, int]], dict[int, dict[str, Any]], str]:
    """Execute search and return results."""
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

    # Build result collections
    table_rows: list[list[object]] = []
    options: list[tuple[str, int]] = []
    mapping: dict[int, dict[str, Any]] = {}

    for it in res.items:
        # Build table row with 8 columns matching Dataframe headers:
        # ID, Brand, MPN, Fornitore, Prezzo, Stock, Lead (gg), Score
        table_row: list[object] = [
            it.id,
            it.brand,
            it.mpn,
            it.supplier,
            round(it.price, 2),
            "Sì" if it.in_stock else "No",
            it.lead_time_days or "-",
            round(it.score, 3),
        ]
        table_rows.append(table_row)

        # Build option for dropdown with format: "{id} · {brand} {mpn} · {supplier} · €{price}"
        # This format is required by _on_select and _on_add which parse the ID from label
        label = f"{it.id} · {it.brand} {it.mpn} · {it.supplier} · €{it.price:.2f}"
        options.append((label, it.id))

        # Build mapping from offer ID (int) to full details dict
        # Required by _on_select and _on_add for cart/preview functionality
        mapping[it.id] = {
            "brand": it.brand,
            "mpn": it.mpn,
            "supplier": it.supplier,
            "price": it.price,
        }

    msg = f"Trovate {len(table_rows)} offerte"
    return table_rows, options, mapping, msg


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

    Business logic that:
    1. Executes search via _do_search()
    2. Fetches facets from API
    3. Processes facets and builds UI state
    4. Returns SearchHandlerResult

    Args:
        query: Search query text
        speed: Current speed filter selection
        freehub: Current freehub filter selection
        brake: Current brake filter selection
        axle: Current axle filter selection
        rotor: Current rotor filter selection
        budget: Budget limit as string (or None)
        category: Selected category filter
        suppliers_sel: List of selected supplier names
        in_stock_only: Whether to filter for in-stock items only

    Returns:
        SearchHandlerResult with all data needed to update UI components
    """
    # Convert budget string to float
    budget_float = _parse_budget(budget)

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

    # Build offer labels for dropdown
    labels = [opt[0] for opt in options]
    default_label = labels[0] if labels else None

    # Default facet updates (used if API call fails)
    # Preserve current filter state to keep UI consistent with search results
    speed_update = FacetUpdate(["", speed] if speed else [""], speed, None, True)
    freehub_update = FacetUpdate(
        ["", freehub] if freehub else [""], freehub, None, True
    )
    brake_update = FacetUpdate(["", brake] if brake else [""], brake, None, True)
    rotor_update = FacetUpdate(["", rotor] if rotor else [""], rotor, None, True)
    axle_update = FacetUpdate(["", axle] if axle else [""], axle, None, True)
    suppliers_choices: list[str] = list(suppliers_sel or [])
    category_update = FacetUpdate(
        ["", category] if category else [""], category, None, True
    )
    # Preserve budget state if set
    if budget_float is not None and budget_float > 0:
        budget_update = BudgetUpdate(
            None, 0, max(100, int(budget_float)), int(budget_float)
        )
    else:
        budget_update = BudgetUpdate(None, 0, 100, 0)

    # Fetch facets from API to refresh filter options/info
    try:
        payload = {
            "query_text": query or None,
            "speed": speed or None,
            "freehub": (freehub or None),
            "brake": (brake or None),
            "axle": axle or None,
            "rotor": (rotor or None),
            "budget_max": budget_float,
            "category": category or None,
            "suppliers": suppliers_sel or [],
            "in_stock_only": bool(in_stock_only),
        }
        r = api_post_silent("/facets", payload, timeout=10)

        if r.status_code == 200:
            f = r.json()

            # Build info strings for each facet
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

            # Extract choices (only keys with count>0 to avoid dead filters)
            speed_choices = sorted(list(f.get("speed", {}).keys()))
            freehub_choices = sorted(list(f.get("freehub", {}).keys()))
            brake_choices = sorted(list(f.get("brake", {}).keys()))
            rotor_choices = sorted(list(f.get("rotor", {}).keys()))
            category_choices = sorted(list(f.get("category", {}).keys()))

            # Coverage gating based on product totals
            totals = f.get("totals", {})
            prod_total = int(totals.get("products", 0) or 0) or 1

            # Reset value to "" if current selection disappears from choices
            speed_val = speed if speed in speed_choices else ""
            freehub_val = freehub if freehub in freehub_choices else ""
            brake_val = brake if brake in brake_choices else ""
            rotor_val = rotor if rotor in rotor_choices else ""
            category_val = category if category in category_choices else ""

            # Calculate coverage for each facet
            cov_speed = calculate_coverage(f.get("speed", {}), prod_total)
            cov_freehub = calculate_coverage(f.get("freehub", {}), prod_total)
            cov_brake = calculate_coverage(f.get("brake", {}), prod_total)
            cov_rotor = calculate_coverage(f.get("rotor", {}), prod_total)

            # Build facet updates with coverage gating (15% threshold)
            speed_update = FacetUpdate(
                choices=[""] + speed_choices,
                value=speed_val,
                info=annotate_low_coverage((speed_info or None), cov_speed),
                interactive=(cov_speed >= FACET_COVERAGE_THRESHOLD),
                coverage=cov_speed,
            )

            freehub_update = FacetUpdate(
                choices=[""] + freehub_choices,
                value=freehub_val,
                info=annotate_low_coverage((freehub_info or None), cov_freehub),
                interactive=(cov_freehub >= FACET_COVERAGE_THRESHOLD),
                coverage=cov_freehub,
            )

            brake_update = FacetUpdate(
                choices=[""] + brake_choices,
                value=brake_val,
                info=annotate_low_coverage((brake_info or None), cov_brake),
                interactive=(cov_brake >= FACET_COVERAGE_THRESHOLD),
                coverage=cov_brake,
            )

            rotor_update = FacetUpdate(
                choices=[""] + rotor_choices,
                value=rotor_val,
                info=annotate_low_coverage((rotor_info or None), cov_rotor),
                interactive=(cov_rotor >= FACET_COVERAGE_THRESHOLD),
                coverage=cov_rotor,
            )

            # Axle facet is always interactive (no coverage gating)
            # Unlike other facets, axle supports free-text input and only shows tooltip info
            axle_update = FacetUpdate(
                choices=[""] + sorted(list(f.get("axle", {}).keys())),
                value=None,
                info=(axle_info or None),
                interactive=True,
            )

            suppliers_choices = sorted(list(f.get("supplier", {}).keys()))

            category_update = FacetUpdate(
                choices=[""] + category_choices,
                value=category_val,
                info=(None if category_choices else "Nessuna categoria nei risultati"),
                interactive=bool(category_choices),
            )

            # Budget/price range updates
            price = f.get("price", {})
            price_info = None
            if price and price.get("max") is not None and price.get("min") is not None:
                price_info = f"Prezzo min/max: €{float(price['min']):.2f} – €{float(price['max']):.2f}"

            max_val = float(price.get("max") or 0.0)

            # If budget is None or 0, keep slider at 0; else clamp in [min,max]
            if budget_float is None:
                slider_val = 0
            else:
                slider_val = max(min(int(budget_float), int(max_val)), 0)

            budget_update = BudgetUpdate(
                info=price_info,
                slider_min=0,
                slider_max=max(100, int(max_val) or 100),
                slider_value=slider_val,
            )

    except Exception as exc:
        log_exception("ui", "facets", "failed to build facets", exc)
        # Use default empty updates set above

    # Build active filters list
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
