Bike Copilot Demo (Lite)

Goal: local demo to ingest parts lists from CSV (later PDF/web), normalize/dedup into SQLite, search with ranking, and generate quotes. This repo is structured to extend sources via provider adapters without reengineering the core.

Quick start
- Use `uv` for running and gates. If `uv` isn’t installed, follow https://docs.astral.sh/uv/ to install.

Makefile targets
- `make status` – run ruff fix/format and basedpyright typecheck.
- `make api` – run the FastAPI app.
- `make seed` – seed demo data.

Directories
- `app/` – code (typed contracts, models, adapters, services).
- `data/demo/` – example CSVs.
- `scripts/` – install/seed helpers.
- `deploy/` – systemd example.

Notes
- Python runs via `uv run ...` in development.
- Boundaries use typed request/response models; no untyped dicts cross edges.

