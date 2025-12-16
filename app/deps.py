from __future__ import annotations

from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy.orm import Session
from importlib import import_module


def get_db() -> Generator[Session, None, None]:
    """Provide a request-scoped database session with automatic cleanup."""
    SessionLocal = import_module("app.models").SessionLocal  # fetch latest binding
    with SessionLocal() as db:
        yield db


# Typed alias for FastAPI dependency injection
SessionDep = Annotated[Session, Depends(get_db)]
