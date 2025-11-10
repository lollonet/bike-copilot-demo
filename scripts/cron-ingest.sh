#!/usr/bin/env bash
set -euo pipefail

# Re-ingest CSV demo files if present.
if [ -f "data/demo/products.csv" ] && [ -f "data/demo/offers.csv" ]; then
  uv run python -m app.ingest --products data/demo/products.csv --offers data/demo/offers.csv
fi

# Example PDF ingest (uncomment and adjust mapping/provider)
# uv run python -m app.ingest_pdf --pdf /path/to/catalog.pdf --mapping providers/example.yaml --provider ExamplePDF

