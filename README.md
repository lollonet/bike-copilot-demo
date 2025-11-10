Bike Copilot Demo (Lite)

Goal: local demo to ingest parts lists from CSV (later PDF/web), normalize/dedup into SQLite, search with ranking, and generate quotes. This repo is structured to extend sources via provider adapters without reengineering the core.

Quick start
- Use `uv` for running and gates. If `uv` isn’t installed, follow https://docs.astral.sh/uv/ to install.

Makefile targets
- `make status` – ruff fix/format + basedpyright typecheck.
- `make test` – run pytest with correct env/cache.
- `make seed` – seed demo CSVs into SQLite.
- `make api` – run FastAPI on `:8000`.
- `make ui` – run Gradio UI on `:7860`.
- CLI help: `uv run python -m app.cli --help`.

Demo script (2 minutes)
- `uv pip install -r requirements.txt`
- `cp .env.example .env` (optional: edit VAT/auth)
- `make seed`
- `make api` then in another shell:
  - Search: `curl -s http://localhost:8000/search -X POST -H 'content-type: application/json' -d '{"speed":"11"}' | jq`
  - Quote: `curl -s -u demo:demo123 http://localhost:8000/quote -X POST -H 'content-type: application/json' -d '{"offer_id":1,"customer_name":"Mario","customer_contact":"mario@example.com"}' | jq`
  - KPI: `curl -s -u demo:demo123 http://localhost:8000/kpi/today | jq`
  - Files (protected): `curl -I -u demo:demo123 http://localhost:8000/files/QUOTE-YYYYMMDD-HHMM.pdf`

Environment
- Copy `.env.example` to `.env` and adjust as needed.
- Key vars: `APP_DB_URL`, `APP_OUT_DIR`, `APP_VAT`, `APP_BASIC_USER`, `APP_BASIC_PASS`.

Health
- `GET /health` → `{status:'ok', db:true, pdfkit:<bool>, version:'<x.y.z>'}`; responses include `X-Trace-Id` header.

CLI Autocomplete
- Show script: `uv run python -m app.cli --show-completion`
- Install: `uv run python -m app.cli --install-completion`
- After install, TAB completes commands/params; `--offer-id` dynamically completes from DB.

CLI Examples
- Ingest CSV: `uv run python -m app.cli ingest-csv --products data/demo/products.csv --offers data/demo/offers.csv`
- Search: `uv run python -m app.cli search-cli --speed 11 --freehub HG`
- Quote (with offer completion): `uv run python -m app.cli quote-cli --offer-id <TAB> --customer-name Mario --customer-contact mario@example.com`
- UI: `uv run python -m app.cli ui`
- API: `uv run python -m app.cli api`

PDF Ingest
- Example: `uv run python -m app.ingest_pdf --pdf /path/to/catalog.pdf --mapping providers/example.yaml --provider ExamplePDF`
- Provide a mapping YAML that defines column → canonical field.

Web Ingest (HTML mapping)
- Example: `uv run python -m app.cli fetch-web --html providers/html/example.html --mapping providers/web-example.yaml`
- Mapping YAML defines CSS selectors for `root`, `brand`, `mpn`, `name`, `price` (and optional `in_stock`, `lead_time_days`).

Security
- Basic Auth guards `/quote`, `/kpi/*`, and `/files/*` when `APP_BASIC_USER` and `APP_BASIC_PASS` are set.
- `/files/*` serves only `.html` and `.pdf` from `APP_OUT_DIR`.

Quote customization
- Optional env: `APP_SHOP_NAME`, `APP_SHOP_ADDRESS`, `APP_SHOP_CONTACT`, `APP_SHOP_LOGO` (path/URL) for header in the PDF/HTML.

Systemd (example)
- Service file: `deploy/bike-copilot.service` (uses `EnvironmentFile=/etc/default/bike-copilot-demo`).
- Steps:
  1. `sudo mkdir -p /opt/bike-copilot-demo`
  2. `sudo rsync -a --exclude .venv ./ /opt/bike-copilot-demo/`
  3. `cd /opt/bike-copilot-demo && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && bash scripts/seed_demo.sh`
  4. `echo "APP_VAT=0.22" | sudo tee /etc/default/bike-copilot-demo`
  5. `sudo cp deploy/bike-copilot.service /etc/systemd/system/`
  6. `sudo systemctl daemon-reload && sudo systemctl enable --now bike-copilot.service`

Scheduled ingest
- `scripts/cron-ingest.sh` re-ingests CSVs; extend to PDFs as needed.

Directories
- `app/` – code (typed contracts, models, adapters, services).
- `data/demo/` – example CSVs.
- `scripts/` – install/seed helpers.
- `deploy/` – systemd example.

Notes
- Python runs via `uv run ...` in development.
- Boundaries use typed request/response models; no untyped dicts cross edges.
