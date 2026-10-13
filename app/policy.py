"""Dealer shipping policy extractor (deterministic, regex-based).

All comments in English; UI strings remain Italian.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .logging_utils import log_event


EUR_RE: Final[re.Pattern[str]] = re.compile(r"€\s*([0-9]+(?:[\.,][0-9]{1,2})?)")
THRESHOLD_HINTS: Final[tuple[str, ...]] = (
    "oltre",
    "superiori a",
    "superiore a",
    "da",
    "free over",
)


@dataclass(frozen=True)
class PolicyExtract:
    base_cost: float | None
    free_threshold: float | None
    lead_days_std: int | None
    confidence: float


def _to_float(txt: str) -> float | None:
    t = txt.replace(" ", "").replace(",", ".")
    try:
        return float(t)
    except (TypeError, ValueError):
        return None


def parse_policy_html(html: str) -> PolicyExtract:
    """Parse shipping policy page and extract base_cost, free_threshold, and lead_days.

    Heuristics:
    - base_cost: the smallest euro amount near words like "spedizione" without threshold hints.
    - free_threshold: the euro amount in a sentence containing hints like "gratuita oltre/superiori a".
    - lead_days_std: detect patterns like 24-48 ore (→ 2) or "entro X giorni".
    Confidence increases when both cost and threshold are found.
    """
    text = _normalized_policy_text(html)
    lead = _extract_lead_days(text)
    free = _extract_free_threshold(text)
    base = _extract_base_cost(text, free)
    conf = _compute_confidence(base, free, lead)
    log_event(
        "DEBUG",
        op="policy",
        kind="extraction",
        message="Extracted shipping policy values",
        extra={
            "base_cost": base,
            "free_threshold": free,
            "lead_days": lead,
            "snippet": text[:200],
        },
    )

    return PolicyExtract(
        base_cost=base, free_threshold=free, lead_days_std=lead, confidence=conf
    )


def _normalized_policy_text(html: str) -> str:
    return re.sub(r"\s+", " ", html, flags=re.M).lower()


def _extract_lead_days(text: str) -> int | None:
    # Lead time: 24-48 ore → 2; entro X giorni → X
    m = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*ore", text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return max(1, round((lo + hi) / 24 / 2))
    m2 = re.search(r"entro\s*(\d{1,2})\s*giorni", text)
    if m2:
        return int(m2.group(1))
    return None


def _extract_free_threshold(text: str) -> float | None:
    free: float | None = None
    for sent in re.split(r"[\.!?]", text):
        if "gratuit" in sent or "gratis" in sent:
            if any(h in sent for h in THRESHOLD_HINTS):
                m3 = EUR_RE.search(sent)
                if m3:
                    free = _to_float(m3.group(1))
                    break
    return free


def _extract_base_cost(text: str, free: float | None) -> float | None:
    # Base cost: prefer euro amounts near shipping hints and not near free/threshold hints
    shipping_hints = ("spedizion", "shipping", "costo", "cost")
    sentences = re.split(r"[\.!?]", text)
    candidates: list[float] = []
    values_all: list[float] = []
    for sent in sentences:
        euros = [_to_float(x) for x in EUR_RE.findall(sent)]
        values = [e for e in euros if e is not None]
        if not values:
            continue
        if any(h in sent for h in ("gratuit", "gratis")) and any(
            h in sent for h in THRESHOLD_HINTS
        ):
            # sentence about free threshold; skip for base determination
            continue
        if any(h in sent for h in shipping_hints):
            candidates.append(min(values))
    base: float | None = min(candidates) if candidates else None

    # Fallback: use global minimum if nothing matched
    if base is None:
        euros_all = [_to_float(x) for x in EUR_RE.findall(text)]
        values_all = [e for e in euros_all if e is not None]
        base = min(values_all) if values_all else None

    if free and base and base >= free:
        # swap: if min is actually threshold, try second min from candidates/all
        ordered = sorted(
            candidates if candidates else [e for e in values_all if e is not None]
        )
        base = ordered[1] if len(ordered) > 1 else None
    return base


def _compute_confidence(
    base: float | None,
    free: float | None,
    lead: int | None,
) -> float:
    conf = 0.5
    if base is not None:
        conf += 0.2
    if free is not None:
        conf += 0.2
    if lead is not None:
        conf += 0.1
    return min(1.0, conf)


def _shipping_policy_from_html(html: str) -> tuple[float, float, int, float]:
    """Backward-compatible wrapper used by legacy callers; kept for tests."""
    base_raw = _extract_base_cost(html, None)
    free_raw = _extract_free_threshold(html)
    lead_raw = _extract_lead_days(_normalized_policy_text(html))
    conf = _compute_confidence(base_raw, free_raw, lead_raw)
    base_val: float = float(base_raw) if base_raw is not None else 0.0
    free_val: float = float(free_raw) if free_raw is not None else 0.0
    lead_val: int = int(lead_raw) if lead_raw is not None else 0
    base: float = base_val
    free_thr: float = free_val
    lead_days: int = lead_val
    return base, free_thr, lead_days, conf
