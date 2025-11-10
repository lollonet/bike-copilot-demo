from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from sqlalchemy.orm import Session

from .models import RawIngest, SessionLocal


HASH_CHUNK: Final[int] = 1024 * 64


def _sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(HASH_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def stage_file(provider: str, kind: str, path: Path) -> RawIngest:
    digest = _sha256_path(path)
    with SessionLocal() as db:  # type: Session
        entry = RawIngest(provider=provider, kind=kind, uri=str(path), content_hash=digest, stored_path=str(path))
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

