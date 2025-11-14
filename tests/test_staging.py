from __future__ import annotations

import os
from pathlib import Path
import importlib


def _setup_db(tmp_name: str):
    os.environ["APP_DB_URL"] = f"sqlite:///./{tmp_name}"
    # Reload config/models/staging so SessionLocal binds to the fresh DB URL.
    import app.config as app_config
    import app.models as app_models
    import app.staging as app_staging

    importlib.reload(app_config)
    importlib.reload(app_models)
    importlib.reload(app_staging)
    from app.models import RawIngest, SessionLocal, create_all

    # Clean previous DB files if any.
    db_file = Path(tmp_name)
    for suffix in ("", "-shm", "-wal"):
        p = db_file.with_name(db_file.name + suffix)
        if p.exists():
            p.unlink()

    create_all()
    return RawIngest, SessionLocal


def test_sha256_path_and_stage_file(tmp_path: Path) -> None:
    from app.staging import _sha256_path, stage_file
    from hashlib import sha256

    RawIngest, SessionLocal = _setup_db("test_staging.db")

    test_file = tmp_path / "sample.txt"
    content = b"hello-bike-copilot"
    test_file.write_bytes(content)

    # Hash helper produces standard SHA256 hex digest.
    digest = _sha256_path(test_file)
    assert digest == sha256(content).hexdigest()

    # stage_file should persist a RawIngest row with matching content_hash.
    entry = stage_file(provider="TestProvider", kind="products", path=test_file)

    assert entry.provider == "TestProvider"
    assert entry.kind == "products"
    assert entry.uri == str(test_file)
    assert entry.content_hash == digest

    with SessionLocal() as db:
        rows = db.query(RawIngest).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.id == entry.id
        assert row.content_hash == digest
