SHELL := /bin/bash

status:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uvx ruff check --fix || true
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uvx ruff format || true
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uvx basedpyright --level error app || true

api:
	uv run uvicorn app.api:app --host 0.0.0.0 --port 8000

seed:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli ingest-csv-mapped --csv catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml

ui:
	uv run python bin/run_ui.py

# PN-first UI (porta :7861)
ui-pn:
	uv run python bin/run_ui_pn.py

test:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run pytest -q

.PHONY: crawl-montanini crawl-ciclodiffusione

crawl-montanini:
	@echo "Crawl Cicli Montanini (WooCommerce) with safe delays"
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli fetch-sitemap --sitemap https://www.ciclimontanini.com/product-sitemap.xml --mapping providers/web-ciclimontanini.yaml --contains /prodotto/ --delay 0.75
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli fetch-sitemap --sitemap https://www.ciclimontanini.com/product-sitemap2.xml --mapping providers/web-ciclimontanini.yaml --contains /prodotto/ --delay 0.75

# Usage: make crawl-ciclodiffusione Q="sella casco catena"
crawl-ciclodiffusione:
	@echo "Crawl Ciclodiffusione (Storeden) for queries: $(Q)"
	@for q in $(Q); do \
		echo "-- $$q"; \
		UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli search-web --query "$$q" --mapping providers/web-ciclodiffusione.yaml --max-pages 5 --delay 0.8; \
	done

# Convenience wrapper: crawl providers with optional queries (defaults provided)
# NOTE: keep unquoted so Make for-loop splits into separate queries.
Q ?= copertone sella casco catena
PROGRESS_INTERVAL ?= 60
web-crawl: crawl-montanini crawl-ciclodiffusione
	@echo "Web crawl completed with queries: $(Q)"

# Alias per retrocompatibilità con README (dealer synchronization)
crawl: web-crawl

# Optional crawls for authenticated dealers (require env creds; otherwise skip)
.PHONY: crawl-rms crawl-ciclopromo all-dealers-crawl ingest-all

crawl-rms:
	@if [ -z "$$DEALER_RMS_AUTH_MODE" ]; then \
		echo "Skipping RMS: set DEALER_RMS_* env vars (see providers/dealers.yaml)"; \
	else \
		UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. bash -lc $$'uv run python - <<PY\nfrom app.cli import fetch_and_parse_urls\nfrom pathlib import Path\nimport yaml\n\nmapping = Path(\"providers/web-rms.yaml\")\ndata = yaml.safe_load(Path(\"providers/dealers.yaml\").read_text(encoding=\"utf-8\")) or {}\nurls = []\nfor d in data.get(\"dealers\", []):\n    if d.get(\"key\") == \"rms\":\n        urls = d.get(\"seeds\", {}).get(\"urls\", [])\n        break\n\nif not urls:\n    print(\"No RMS seed URLs configured; skipping\")\nelse:\n    products, offers = fetch_and_parse_urls(urls, mapping)\n    from app.ingest import upsert\n    stats = upsert(products, offers)\n    print(stats)\nPY'; \
	fi

crawl-ciclopromo:
	@if [ -z "$$DEALER_CICLOPROMO_AUTH_MODE" ]; then \
		echo "Skipping CicloPromo: set DEALER_CICLOPROMO_* env vars (see providers/dealers.yaml)"; \
	else \
		UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. bash -lc $$'uv run python - <<PY\nfrom app.cli import fetch_and_parse_urls\nfrom pathlib import Path\nimport yaml\n\nmapping = Path(\"providers/web-ciclopromo.yaml\")\ndata = yaml.safe_load(Path(\"providers/dealers.yaml\").read_text(encoding=\"utf-8\")) or {}\nurls = []\nfor d in data.get(\"dealers\", []):\n    if d.get(\"key\") == \"ciclopromo\":\n        urls = d.get(\"seeds\", {}).get(\"urls\", [])\n        break\n\nif not urls:\n    print(\"No CicloPromo seed URLs configured; skipping\")\nelse:\n    products, offers = fetch_and_parse_urls(urls, mapping)\n    from app.ingest import upsert\n    stats = upsert(products, offers)\n    print(stats)\nPY'; \
	fi

all-dealers-crawl: crawl-montanini crawl-ciclodiffusione crawl-rms crawl-ciclopromo
	@echo "All dealer crawls completed with queries: $(Q)"

# Full ingest: seed CSV demo + crawls (auth dealers skipped if env assente)
ingest-all ingest-all-parallel:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli ingest-all-parallel --queries "$(Q)" --max-pages 5 --delay 0.8 --progress-interval $(PROGRESS_INTERVAL)

.PHONY: reconcile-offers
# Reconciliation: mark offers missing after crawl as stale (soft-delete flag) for all suppliers in DB
reconcile-offers:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. bash -lc $$'uv run python - <<PY\nfrom app import models\nfrom sqlalchemy import select\nfrom datetime import datetime, timezone, timedelta\nimport os\n\nmodels.create_all()\nengine = models.get_engine()\nstale_days = float(os.environ.get(\"STALE_DAYS\", \"3\"))\ncutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)\nwith engine.begin() as conn:\n    if \"stale\" not in [c[1] for c in conn.exec_driver_sql(\"PRAGMA table_info(supplier_offer)\").fetchall()]:\n        conn.exec_driver_sql(\"ALTER TABLE supplier_offer ADD COLUMN stale BOOLEAN DEFAULT 0\")\n\n    # Mark offers older than cutoff as stale (per-supplier latest no longer used)\n    res = conn.exec_driver_sql(\n        \"UPDATE supplier_offer SET stale = 1 WHERE updated_at < ?\",\n        (cutoff,),\n    )\n    stale_count = conn.exec_driver_sql(\"SELECT COUNT(*) FROM supplier_offer WHERE stale = 1\").scalar_one()\n    print({\"op\": \"reconcile-offers\", \"stale_marked\": stale_count, \"cutoff\": cutoff.isoformat(), \"stale_days\": stale_days})\nPY'

.PHONY: reset-db
reset-db:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. bash -lc $$'uv run python - <<PY\nfrom app import models\nimport os\n\nurl = models.settings.db_url\nif url.startswith(\"sqlite\"):\n    path = url.split(\"///\")[-1]\n    for p in [path, f\"{path}-shm\", f\"{path}-wal\"]:\n        if os.path.exists(p):\n            os.remove(p)\nmodels.create_all()\nprint({\"op\": \"reset-db\", \"url\": url})\nPY'
# Fetch a JS/login page rendered via Playwright (requires playwright installed)
WAIT_MS ?= 1500
fetch-rendered:
	@if [ -z "$(URL)" ]; then echo "Missing URL. Usage: make fetch-rendered URL=https://example.com [WAIT_MS=1500]"; exit 1; fi
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli fetch-rendered --url "$(URL)" --wait-ms $(WAIT_MS)
