# Session 2025-12-17 — Parallel ingest orchestration

- REQ-007: added CLI `ingest-all-parallel` with per-provider file locks, minute-by-minute status output, and parallel crawls (Montanini, Ciclodiffusione, RMS, CicloPromo).
- Makefile `ingest-all` now delegates to the new CLI; `PROGRESS_INTERVAL` env allows tuning status cadence; keeps query override via `Q`.
- README essential commands updated to reflect parallel ingest/status.
- Verification run: `make status` (ruff/format/basedpyright) and `make test` (pytest) both green.
- Bugfix 17:45 UTC — CLI now loads `.env` automatically (`load_dotenv`) so dealer auth vars (DEALER_RMS_AUTH_MODE, DEALER_CICLOPROMO_AUTH_MODE, etc.) are detected when present locally.
- REQ-004/REQ-005: PN-first UI refreshed with two-column layout, checkbox selection in results, cart cost summary (shipping + APP_VAT toggle), and quote notes placed next to the action buttons.
- Verification: `uvx ruff check app/ui_pn.py`; `uvx ruff format app/ui_pn.py`; `uvx basedpyright --level error app/ui_pn.py`; `uv run pytest -q` (76 passed).
- Assessment 2025-12-18 (bugfix sweep, see assessment/skeptic-review-bugfix-prompt-2025-12-18.md):
  - CRITICAL: hardened `/files/{path}` against traversal (middleware + path validation; returns 403 on dotfiles/../etc) and added tests.
  - HIGH: guarded `_common_dealers` empty input; fixed lambda late-binding in `ingest-all-parallel`; `_load_synonyms` now tolerates missing file; offers `updated_at` refreshed on upsert.
  - MEDIUM: template loader uses path-relative templates; sitemap recursion capped; offer upsert uses SQLite `ON CONFLICT DO UPDATE`; price parser returns 0 on bad input; policy extractor logs and improves base/threshold heuristics; reconciliation marks missing offers out-of-stock; playwright browser always closed; division-by-zero guarded in ranking.
  - Tests: `uvx ruff check app/`; `uvx ruff format --check app/`; `uvx basedpyright --level error app/`; `uv run pytest -v --tb=short` (77 passed).
