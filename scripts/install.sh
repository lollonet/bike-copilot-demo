#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install from https://docs.astral.sh/uv/" >&2
  exit 1
fi

uv run python -c "print('Python via uv is ready')"

uv pip install -r requirements.txt

chmod +x scripts/seed_demo.sh
uv run bash scripts/seed_demo.sh

echo "Install complete. Run API with: make api"

