status:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uvx ruff check --fix || true
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uvx ruff format || true
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uvx basedpyright --level error app || true

api:
	uv run uvicorn app.api:app --host 0.0.0.0 --port 8000

seed:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli ingest-csv-mapped --csv catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml

ui:
	uv run python -m app.ui

# PN-first UI (porta :7861)
ui-pn:
	uv run python -m app.ui_pn

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
		UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli search-web --query "$$q" --mapping providers/web-ciclodiffusione.yaml --max-pages 3 --delay 0.8; \
	done

# Convenience wrapper: crawl providers with optional queries (defaults provided)
# NOTE: keep unquoted so Make for-loop splits into separate queries.
Q ?= copertone sella casco catena
web-crawl: crawl-montanini crawl-ciclodiffusione
	@echo "Web crawl completed with queries: $(Q)"

# Fetch a JS/login page rendered via Playwright (requires playwright installed)
WAIT_MS ?= 1500
fetch-rendered:
	@if [ -z "$(URL)" ]; then echo "Missing URL. Usage: make fetch-rendered URL=https://example.com [WAIT_MS=1500]"; exit 1; fi
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.cli fetch-rendered --url "$(URL)" --wait-ms $(WAIT_MS)
