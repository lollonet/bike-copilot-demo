#!/usr/bin/env bash
set -euo pipefail

# Project status command: runs lint/format/typecheck via uvx.
# Default: check-only (no modifications). Use --fix to apply ruff fixes and format.

run_fix=false
if [[ "${1-}" == "--fix" ]]; then
  run_fix=true
fi

export UV_CACHE_DIR="${UV_CACHE_DIR:-$(pwd)/.cache/uv}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-$(pwd)/.cache/uv/tools}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$(pwd)/.cache/uv/python}"
mkdir -p "$UV_CACHE_DIR" "$UV_TOOL_DIR" "$UV_PYTHON_INSTALL_DIR"
echo "[status] Using uvx from PATH: $(command -v uvx || echo 'uvx not found')"
echo "[status] UV_CACHE_DIR=$UV_CACHE_DIR"
echo "[status] UV_TOOL_DIR=$UV_TOOL_DIR"
echo "[status] UV_PYTHON_INSTALL_DIR=$UV_PYTHON_INSTALL_DIR"

if [[ "$run_fix" == true ]]; then
  echo "[status] Running ruff check --fix ..."
  uvx ruff check --fix
  echo "[status] Running ruff format ..."
  uvx ruff format
else
  echo "[status] Running ruff check (no-fix) ..."
  uvx ruff check --output-format grouped
  echo "[status] Running ruff format --check ..."
  uvx ruff format --check
fi

echo "[status] Running basedpyright ..."
PY_PATHS=()
[[ -d src ]] && PY_PATHS+=(src)
[[ -d scripts ]] && PY_PATHS+=(scripts)
if [[ ${#PY_PATHS[@]} -eq 0 ]]; then
  echo "[status] No Python paths (src/scripts) found; skipping type check"
else
  uvx basedpyright --level error "${PY_PATHS[@]}"
fi

echo "[status] Done."
