from __future__ import annotations

from pathlib import Path

from app.policy import parse_policy_html


def test_parse_policy_free_threshold_and_base_cost():
    html = Path("providers/html/policy-free49.html").read_text(encoding="utf-8")
    ext = parse_policy_html(html)
    assert ext.base_cost is not None and abs(ext.base_cost - 6.9) < 0.01
    assert ext.free_threshold is not None and abs(ext.free_threshold - 49.0) < 0.01
    assert ext.lead_days_std in (1, 2)
    assert 0.5 <= ext.confidence <= 1.0

