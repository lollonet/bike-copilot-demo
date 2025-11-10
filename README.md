Bike Copilot Demo (Lite)

Goal: local demo to ingest parts lists from CSV (later PDF/web), normalize/dedup into SQLite, search with ranking, and generate quotes. This repo is structured to extend sources via provider adapters without reengineering the core.

Quick start
- Use `uv` for running and gates. If `uv` isn’t installed, follow https://docs.astral.sh/uv/ to install.

Makefile targets
- `make status` – run ruff fix/format and basedpyright typecheck.
- `make api` – run the FastAPI app.
- `make seed` – seed demo data.
- `uv run python -m app.cli --help` – CLI with autocomplete.

Demo script (2 minutes)
- `uv pip install -r requirements.txt`
- `make seed`
- `make api` then in another shell:
  - Search: `curl -s http://localhost:8000/search -X POST -H 'content-type: application/json' -d '{"speed":"11"}' | jq` 
  - Quote: `curl -s -u demo:demo123 http://localhost:8000/quote -X POST -H 'content-type: application/json' -d '{"offer_id":1,"customer_name":"Mario","customer_contact":"mario@example.com"}' | jq`
  - KPI: `curl -s -u demo:demo123 http://localhost:8000/kpi/today | jq`
  - Files: `curl -I -u demo:demo123 http://localhost:8000/files/QUOTE-YYYYMMDD-HHMM.pdf`

Environment
- Copy `.env.example` to `.env` and adjust if needed.

Health
- `GET /health` returns `{status:'ok', db:true, pdfkit:<bool>, version:'<x.y.z>'}`

CLI Autocomplete
- Install completion into your shell session:
  - Show script: `uv run python -m app.cli --show-completion`
  - Install: `uv run python -m app.cli --install-completion`
- Then use tab-completion for commands and parameters, e.g. `--freehub`, `--rotor`, and `--offer-id`.

CLI Examples
- Ingest CSV: `uv run python -m app.cli ingest-csv --products data/demo/products.csv --offers data/demo/offers.csv`
- Search: `uv run python -m app.cli search-cli --speed 11 --freehub HG`
- Quote (with offer completion): `uv run python -m app.cli quote-cli --offer-id <TAB> --customer-name Mario --customer-contact mario@example.com`

Directories
- `app/` – code (typed contracts, models, adapters, services).
- `data/demo/` – example CSVs.
- `scripts/` – install/seed helpers.
- `deploy/` – systemd example.

Notes
- Python runs via `uv run ...` in development.
- Boundaries use typed request/response models; no untyped dicts cross edges.
