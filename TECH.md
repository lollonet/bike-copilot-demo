# tech

## context
Local demo app to ingest supplier lists (CSV now; PDF/web later) into SQLite, search with ranking, and generate quotes. Architecture favors one typed ingest boundary with provider adapters.

## components
- Ingress
  - API: FastAPI (`/health`, `/search`, `/quote` planned, `/kpi` planned)
  - UI: Gradio (planned) for one‑click search and quote
- Services
  - Ingest Orchestrator → calls provider adapters and upserts
  - Search/Ranking → compatibility + price/stock/lead score
  - Quote → HTML→PDF via wkhtmltopdf/pdfkit (HTML fallback)
  - KPI/Logging → `event_log` table and simple counters
- Adapters (provider boundary)
  - CSV Adapter (present)
  - PDF Table Adapter (planned)
  - Web Adapter (planned; API preferred over scraping)
- Persistence
  - SQLite with WAL: `product`, `supplier_offer`, `event_log` (plus staging planned)
  - Files: out/ for quote artifacts

## boundaries & contracts
All external edges use typed models. No untyped dicts cross edges.

### API contracts (Pydantic v2)
```python
# app/types.py
class Problem(BaseModel):
    kind: str; message: str; ts: datetime; trace_id: str | None

class SearchRequest(BaseModel):
    query_text: str | None
    speed: str | None
    freehub: Freehub | None
    brake: Brake | None
    axle: str | None
    rotor: Rotor | None
    budget_max: float | None

class OfferItem(BaseModel):
    id: int; brand: str; mpn: str; supplier: str
    price: float; in_stock: bool; lead_time_days: int | None
    score: float; pros: list[str]; cons: list[str]

class SearchResponse(BaseModel):
    items: list[OfferItem]; ts: datetime

class QuoteRequest(BaseModel):
    offer_id: int; customer_name: str; customer_contact: str
    validity_days: int = 7; notes: str | None

class QuoteResponse(BaseModel):
    content_type: str; html_path: str; pdf_path: str | None
```

### Ingest boundary (adapters → orchestrator)
```python
class ProductInput(BaseModel):
    brand: str; mpn: str; ean: str | None; name: str
    speed: str | None; brake: str | None; axle: str | None
    rotor: str | None; freehub: str | None

class OfferInput(BaseModel):
    brand: str; mpn: str; supplier: str; price: float; in_stock: bool
    lead_time_days: int | None; currency: str | None
    extra: dict[str, str | int | float | bool | None]  # typed, no Any
```

### Data model (SQLite)
- product(id, brand, mpn, ean, name, speed, brake, axle, rotor, freehub)
- supplier_offer(id, product_id, supplier, price, in_stock, lead_time_days, updated_at, currency, extra)
- event_log(id, ts, type, payload)
- Indexes: product(ean), product(brand, mpn), supplier_offer(product_id)

## flows
- Ingest: adapter emits `ProductInput`/`OfferInput` → upsert (prefer EAN, fallback brand+mpn) → new `supplier_offer` rows.
- Search: filter by requested specs → compute compatibility → score: 0.35 avail + 0.25 comp + 0.20 lead + 0.20 price_norm → top‑3.
- Quote: render Jinja2 HTML, optionally pdfkit→PDF; store under `out/` and return paths.
- KPI: log `search` and `quote_created` into `event_log`; `/kpi/today` aggregates.

## failure modes & handling
- Missing wkhtmltopdf: Quote returns HTML only with clear `content_type`.
- DB locked: WAL + `busy_timeout`, serialize ingest vs. live demo.
- CSV/PDF schema drift: per‑provider mapping YAML; validation with explicit problems.
- Parser errors / network: retries with capped backoff (base 250ms, factor 2, cap 8s, attempts 3).
- Auth: Basic Auth only on `/quote` and `/kpi/*`; credentials via `.env` or environment.

## configuration
- Environment
  - `APP_DB_URL` (default `sqlite:///./app.db`)
  - `APP_OUT_DIR` (default `out`)
  - `APP_PREFER_IN_STOCK` (default `1`)
  - `APP_SYNONYMS` (default `app/synonyms.yaml`)
- Files
  - `app/synonyms.yaml` for canonicalization
  - Per‑provider mapping YAML (planned under `providers/`)
- Precedence: run‑level flags → per‑agent settings → code defaults → env

## testing
- Boundary tests
  - `apply_synonyms` normalization
  - Compatibility filter and scoring (stock wins ties)
  - API `/search` happy path via TestClient
- Quote tests
  - HTML creation always; PDF only if wkhtmltopdf present
- Ingest tests
  - CSV adapter: valid/invalid rows; idempotent upsert; EAN preferred
- Coverage target: ≥ 85% line and branch (CONTROL.yaml)

## logging & errors
- Problem model: `{ kind, message, ts, trace_id }` in API error responses; no raw tracebacks.
- Event log: insert `search`, `quote_created` with key payload fields.
- Logs: structured messages with `trace_id` (planned); minimal schema `{ ts, level, trace_id, op, kind, message }`.

## evidence
- Vendor docs (initial list; fill versions after .venv audit):
  - FastAPI, Pydantic v2, SQLAlchemy 2.x, pandas, rapidfuzz, PyYAML, Jinja2, pdfkit/wkhtmltopdf, Gradio, httpx
- .venv audit (to run after `uv pip install -r requirements.txt`):
  - List packages/versions: `uv run python -c "import importlib, pkgutil; print(sorted([(m.name) for m in pkgutil.iter_modules()]))"`
  - Capture versions: `uv run python - <<'PY'\nimport fastapi, pydantic, sqlalchemy, pandas, rapidfuzz, yaml, jinja2, httpx\nprint({'fastapi': fastapi.__version__, 'pydantic': pydantic.__version__, 'sqlalchemy': sqlalchemy.__version__})\nPY`
  - Record citations in this section with runtime paths like `.venv:<path>:<line>` and repo references like `repo:app/types.py:1`.

## capabilities
- http‑framework: FastAPI
- cli‑runner: uv
- validator: Pydantic v2
- orm: SQLAlchemy 2
- dataframes: pandas
- fuzzy‑match: rapidfuzz
- templating: Jinja2
- pdf: pdfkit + wkhtmltopdf
- ui: Gradio
- http‑client: httpx

## operations
- Status: `make status` runs ruff fix/format and basedpyright.
- Run API: `make api`
- Seed demo: `make seed`
- Systemd example: `deploy/bike-copilot.service` (ensure user has write access to `out/`).

