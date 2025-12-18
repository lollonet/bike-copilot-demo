from __future__ import annotations

import json
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_trace_id(trace_id: str | None) -> Token:
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: Token) -> None:
    _trace_id_var.reset(token)


def get_trace_id() -> str | None:
    return _trace_id_var.get()


def log_event(
    level: str,
    op: str,
    kind: str,
    message: str,
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    resolved_trace = trace_id if trace_id is not None else get_trace_id()
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "trace_id": resolved_trace,
        "op": op,
        "kind": kind,
        "message": message,
    }
    if extra:
        rec.update({k: v for k, v in extra.items() if k not in rec})
    print(json.dumps(rec, ensure_ascii=False))


def log_exception(
    op: str,
    kind: str,
    message: str,
    exc: Exception,
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Structured logging helper for caught exceptions."""
    merged = {"err": repr(exc)}
    if extra:
        merged.update(extra)
    log_event(
        "error",
        op=op,
        kind=kind,
        message=message,
        trace_id=trace_id,
        extra=merged,
    )
