#!/usr/bin/env bash
set -euo pipefail

uv run python -m app.ingest --products data/demo/products.csv --offers data/demo/offers.csv

