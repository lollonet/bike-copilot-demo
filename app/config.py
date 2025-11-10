from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_url: str = os.environ.get("APP_DB_URL", "sqlite:///./app.db")
    out_dir: str = os.environ.get("APP_OUT_DIR", "out")
    prefer_in_stock: bool = os.environ.get("APP_PREFER_IN_STOCK", "1") == "1"
    synonyms_path: str = os.environ.get("APP_SYNONYMS", "app/synonyms.yaml")
    basic_user: str = os.environ.get("APP_BASIC_USER", "")
    basic_pass: str = os.environ.get("APP_BASIC_PASS", "")


settings = Settings()
