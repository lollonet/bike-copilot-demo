status:
	uvx ruff check --fix || true
	uvx ruff format || true
	uvx basedpyright --level error app || true

api:
	uv run uvicorn app.api:app --host 0.0.0.0 --port 8000

seed:
	uv run python -m app.ingest --products data/demo/products.csv --offers data/demo/offers.csv

