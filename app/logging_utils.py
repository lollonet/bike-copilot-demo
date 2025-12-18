from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def log_event(
    level: str,
    op: str,
    kind: str,
    message: str,
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "trace_id": trace_id,
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
        "error", op=op, kind=kind, message=message, trace_id=trace_id, extra=merged
    )
