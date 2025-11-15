from __future__ import annotations

import json
from datetime import datetime
from io import StringIO
from typing import Any

import pytest

from app.logging_utils import log_event
from app.types import (
    OptimizeItem,
    OptimizeParams,
    OptimizeRequest,
    Problem,
    QuoteRequest,
    SearchRequest,
)


def test_problem_default_ts_and_trace_id() -> None:
    prob = Problem(kind="error", message="something went wrong")
    assert prob.kind == "error"
    assert prob.message == "something went wrong"
    # ts should be set to a recent datetime
    assert isinstance(prob.ts, datetime)
    assert prob.trace_id is None


def test_search_request_validation() -> None:
    req = SearchRequest(
        query_text="catena",
        speed="11",
        suppliers=["S1", "S2"],
        in_stock_only=True,
    )
    assert req.query_text == "catena"
    assert req.speed == "11"
    assert req.suppliers == ["S1", "S2"]
    assert req.in_stock_only is True


def test_quote_request_requires_items_and_customer() -> None:
    item = QuoteRequest.CartItem(offer_id=1, qty=2)
    req = QuoteRequest(
        items=[item],
        customer_name="Test",
        customer_contact="contact@example.com",
    )
    assert req.items[0].offer_id == 1
    assert req.items[0].qty == 2
    assert req.customer_name == "Test"
    assert req.validity_days == 7


def test_optimize_request_validation() -> None:
    item = OptimizeItem(maker_pn="ABC123", qty=3)
    params = OptimizeParams(scenario="miglior-prezzo", max_dealer=2)
    req = OptimizeRequest(items=[item], params=params)

    assert len(req.items) == 1
    assert req.items[0].maker_pn == "ABC123"
    assert req.items[0].qty == 3
    assert req.params.scenario == "miglior-prezzo"
    assert req.params.max_dealer == 2


def test_log_event_writes_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = StringIO()

    def _fake_print(text: str, *args: Any, **kwargs: Any) -> None:
        buf.write(text)

    monkeypatch.setattr("builtins.print", _fake_print)

    log_event(
        "INFO",
        op="test",
        kind="unit",
        message="hello",
        trace_id="abc123",
        extra={"foo": "bar"},
    )

    raw = buf.getvalue()
    data = json.loads(raw)
    assert data["level"] == "INFO"
    assert data["op"] == "test"
    assert data["kind"] == "unit"
    assert data["message"] == "hello"
    assert data["trace_id"] == "abc123"
    assert data["foo"] == "bar"
    assert "ts" in data
