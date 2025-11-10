status:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run ruff check --fix || true
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run ruff format || true
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run basedpyright --level error app || true

api:
	uv run uvicorn app.api:app --host 0.0.0.0 --port 8000

seed:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run python -m app.ingest --products data/demo/products.csv --offers data/demo/offers.csv

ui:
	uv run python -m app.ui

test:
	UV_CACHE_DIR=.uv-cache XDG_CACHE_HOME=.uv-cache PYTHONPATH=. uv run pytest -q
