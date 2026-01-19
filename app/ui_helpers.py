"""Helper functions for UI layer - extracted from monolithic handlers."""

from __future__ import annotations

from app.logging_utils import log_exception


def active_filters_list(
    category: str | None,
    suppliers_sel: list[str] | None,
    in_stock_only: bool,
    speed: str | None,
    freehub: str | None,
    brake: str | None,
    axle: str | None,
    rotor: str | None,
    budget: str | None,
) -> list[str]:
    """
    Build list of active filter strings for display.

    Args:
        category: Selected category filter
        suppliers_sel: List of selected supplier names
        in_stock_only: Whether to filter for in-stock items only
        speed: Selected speed filter
        freehub: Selected freehub filter
        brake: Selected brake filter
        axle: Selected axle filter
        rotor: Selected rotor filter
        budget: Budget limit as string

    Returns:
        List of formatted filter strings (e.g., ["category:MTB", "in_stock:true"])
    """
    filters: list[str] = []
    if category:
        filters.append(f"category:{category}")
    if suppliers_sel:
        filters.append(f"suppliers:{','.join(sorted(suppliers_sel))}")
    if in_stock_only:
        filters.append("in_stock:true")
    if speed:
        filters.append(f"speed:{speed}")
    if freehub:
        filters.append(f"freehub:{freehub}")
    if brake:
        filters.append(f"brake:{brake}")
    if axle:
        filters.append(f"axle:{axle}")
    if rotor:
        filters.append(f"rotor:{rotor}")
    if budget is not None:
        try:
            bval = float(budget)
        except Exception as exc:
            log_exception(
                "ui",
                "filters",
                "invalid budget value",
                exc,
                extra={"budget": budget},
            )
            bval = 0.0
        if bval > 0:
            filters.append(f"budget:<= {bval:.0f}")
    return filters


def calculate_coverage(counts: dict[str, int], total: int) -> float:
    """
    Calculate coverage ratio of facet counts vs total products.

    Args:
        counts: Dictionary of facet value counts
        total: Total number of products

    Returns:
        Coverage ratio (0.0 to 1.0)
    """
    if total == 0:
        return 0.0
    return sum(int(v) for v in (counts or {}).values()) / float(total)


def annotate_low_coverage(
    info: str | None, coverage: float, threshold: float = 0.15
) -> str | None:
    """
    Add low-coverage warning to info string if coverage below threshold.

    Args:
        info: Original info string
        coverage: Coverage ratio (0.0 to 1.0)
        threshold: Coverage threshold for warning (default: 0.15)

    Returns:
        Original info or info with warning appended
    """
    if not info:
        return None
    return f"{info} — poche specifiche nei risultati" if coverage < threshold else info
