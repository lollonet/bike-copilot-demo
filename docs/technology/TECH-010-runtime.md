---
id: TECH-010
domain: technology
status: approved
source_of_truth: false
related: [TECH-INDEX, ARC-010]
---
Runtime & Environment

Stack
- API/UI/CLI: FastAPI, Gradio, Typer; Python via uv
- Typing/lint/format: Pydantic v2, basedpyright, ruff
- DB: SQLite (WAL), SQLAlchemy 2.x
- ETL: pandas, pdfplumber (PDF), BeautifulSoup/httpx (web)
- Templating/PDF: Jinja2 + wkhtmltopdf/pdfkit (HTML fallback when missing)

Boundaries & Contracts
- All external edges use typed models (see app/types.py). No untyped dicts cross edges.
- Ingest uses provider adapters emitting ProductInput/OfferInput; upsert is idempotent and tracks price history.

Operations
- Scripts: `make status`, `make test`, `make api`, `make ui`
- CI: see ARC-001 and CI workflow for order/gates
- Systemd: deploy/bike-copilot.service; env via `/etc/default/bike-copilot-demo`

Configuration (env)
- APP_DB_URL, APP_OUT_DIR, APP_PREFER_IN_STOCK, APP_SYNONYMS,
  APP_BASIC_USER/APP_BASIC_PASS, APP_VAT

Evidence
- Keep `.venv` audit notes under TECH.md history or session summaries when needed.
