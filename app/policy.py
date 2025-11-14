"""Dealer shipping policy extractor (deterministic, regex-based).

All comments in English; UI strings remain Italian.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


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
    except Exception:
        return None


def parse_policy_html(html: str) -> PolicyExtract:
    """Parse shipping policy page and extract base_cost, free_threshold, and lead_days.

    Heuristics:
    - base_cost: the smallest euro amount near words like "spedizione" without threshold hints.
    - free_threshold: the euro amount in a sentence containing hints like "gratuita oltre/superiori a".
    - lead_days_std: detect patterns like 24-48 ore (→ 2) or "entro X giorni".
    Confidence increases when both cost and threshold are found.
    """
    text = re.sub(r"\s+", " ", html, flags=re.M).lower()

    # Lead time: 24-48 ore → 2; entro X giorni → X
    lead: int | None = None
    m = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*ore", text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        lead = max(1, round((lo + hi) / 24 / 2))
    else:
        m2 = re.search(r"entro\s*(\d{1,2})\s*giorni", text)
        if m2:
            lead = int(m2.group(1))

    # Free threshold
    free: float | None = None
    for sent in re.split(r"[\.!?]", text):
        if "gratuit" in sent or "gratis" in sent:
            if any(h in sent for h in THRESHOLD_HINTS):
                m3 = EUR_RE.search(sent)
                if m3:
                    free = _to_float(m3.group(1))
                    break

    # Base cost: pick the smallest euro not part of threshold sentence
    euros = [_to_float(x) for x in EUR_RE.findall(text)]
    euros = [e for e in euros if e is not None]
    base: float | None = None
    if euros:
        base = min(euros)
        if free and base and base >= free:
            # swap: if min is actually threshold, try second min
            pos = sorted(euros)
            base = pos[1] if len(pos) > 1 else None

    conf = 0.5
    if base is not None:
        conf += 0.2
    if free is not None:
        conf += 0.2
    if lead is not None:
        conf += 0.1
    conf = min(1.0, conf)

    return PolicyExtract(
        base_cost=base, free_threshold=free, lead_days_std=lead, confidence=conf
    )
