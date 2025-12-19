SHELL := /bin/bash

# Configuration
UV_ENV := UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=.
CI_FOLDERS := app tests scripts

## 🚀 Quality & CI
.PHONY: status ci-fast ci-sota lint typecheck test-fast test-legacy test

status: lint typecheck

lint:
	$(UV_ENV) uv run ruff check --fix $(CI_FOLDERS)
	$(UV_ENV) uv run ruff format $(CI_FOLDERS)

typecheck:
	$(UV_ENV) uv run basedpyright --level error app

test-fast:
	$(UV_ENV) uv run pytest -q -m "not slow"

test:
	$(UV_ENV) uv run pytest -v

test-legacy:
	@echo "Running LEGACY tests (quarantined)..."
	$(UV_ENV) uv run pytest tests/_legacy || true

# FAST CI: Pre-commit/Pre-push (Local)
ci-fast: lint typecheck test-fast
	@echo "✅ CI-FAST PASSED"

# SOTA CI: Full verification (Remote/Release)
ci-sota: ci-fast
	$(UV_ENV) uv run python scripts/spec_lint.py
	$(UV_ENV) uv run python scripts/traceability.py
	$(UV_ENV) uv run python scripts/complexity_gate.py --paths app
	$(UV_ENV) uv run bandit -r app/ -x app/_legacy -ll -ii
	@echo "🌟 CI-SOTA PASSED"

## 🛠️ Development
api:
	$(UV_ENV) uv run uvicorn app.api:app --host 0.0.0.0 --port 8000

seed:
	$(UV_ENV) uv run python -m app.cli ingest-csv-mapped --csv data/dump/catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml

ui:
	$(UV_ENV) uv run python -m app.ui

ui-pn:
	$(UV_ENV) uv run python -m app.ui_pn

## 🕷️ Crawling
.PHONY: crawl-montanini crawl-ciclodiffusione crawl-rms crawl-ciclopromo web-crawl crawl all-dealers-crawl

crawl-montanini:
	@echo "Crawl Cicli Montanini..."
	$(UV_ENV) uv run python -m app.cli fetch-sitemap --sitemap https://www.ciclimontanini.com/product-sitemap.xml --mapping providers/web-ciclimontanini.yaml --contains /prodotto/ --delay 0.75

crawl-ciclodiffusione:
	@echo "Crawl Ciclodiffusione for queries: $(Q)"
	@for q in $(Q); do \
		$(UV_ENV) uv run python -m app.cli search-web --query "$$q" --mapping providers/web-ciclodiffusione.yaml --max-pages 5 --delay 0.8; \
	done

# Stub targets for removed providers (to fix all-dealers-crawl)
crawl-rms:
	@echo "Skipping RMS (legacy provider logic moved)"

crawl-ciclopromo:
	@echo "Skipping CicloPromo (legacy provider logic moved)"

Q ?= copertone sella casco catena
web-crawl: crawl-montanini crawl-ciclodiffusione
crawl: web-crawl

all-dealers-crawl: crawl-montanini crawl-ciclodiffusione crawl-rms crawl-ciclopromo

## 🧹 Maintenance
.PHONY: reconcile-offers reset-db

reconcile-offers:
	$(UV_ENV) uv run python -m app.cli reconcile-offers

reset-db:
	$(UV_ENV) uv run python -m app.cli reset-db

# Legacy / Utils
fetch-rendered:
	@if [ -z "$(URL)" ]; then echo "Usage: make fetch-rendered URL=..."; exit 1; fi
	$(UV_ENV) uv run python -m app.cli fetch-rendered --url "$(URL)" --wait-ms 1500
