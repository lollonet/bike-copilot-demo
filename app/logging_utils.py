from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
import contextvars

_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)


def set_trace_id(trace_id: str | None) -> None:
    _trace_id_var.set(trace_id)


def log_event(
    level: str,
    op: str,
    kind: str,
    message: str,
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    resolved_trace = trace_id if trace_id is not None else _trace_id_var.get()
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
    resolved_trace = trace_id if trace_id is not None else _trace_id_var.get()
    merged = {"err": repr(exc)}
    if extra:
        merged.update(extra)
    log_event(
        "error",
        op=op,
        kind=kind,
        message=message,
        trace_id=resolved_trace,
        extra=merged,
    )
