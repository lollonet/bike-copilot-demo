---
id: ARC-010
domain: architecture
status: approved
source_of_truth: false
related: [ARC-INDEX, TECH-010]
---
Architecture Overview

1) Context
Local demo to ingest supplier lists (CSV now; PDF/Web next) into SQLite, search with ranking, and generate quotes. Clear typed boundaries, one path per behavior.

2) Components
- Ingest (CSV/PDF/Web adapters) → idempotent upsert
- Metacatalog (SQLite, WAL): product, supplier_offer, event_log, raw_ingest, price_history
- Search/Ranking: compatibility + availability/lead/price score
- API/UI/CLI: FastAPI endpoints; Gradio UI; Typer CLI with autocomplete
- Quote: Jinja2 HTML, optional PDF via wkhtmltopdf/pdfkit
- Ops: systemd service, out/ artifacts, KPI endpoint

3) Data model (essential)
- product(id, brand, mpn, ean, name, speed, brake, axle, rotor, freehub, category)
- supplier_offer(id, product_id, supplier, price, in_stock, lead_time_days, updated_at, currency, extra)
- event_log(id, ts, type, payload)
- raw_ingest(id, ts, provider, kind, uri, content_hash, stored_path)
- price_history(id, ts, offer_id, price, source_hash)

4) Interfaces
- API: `/health`, `/search`, `/facets`, `/quote`, `/files/{name}`, `/kpi/today`
- CLI: `ingest-*`, `search-cli`, `quote-cli`, `ui`, `api`
- UI: Gradio Blocks; cart + multi‑item quotes

5) Quality
- Ingest is idempotent; price change tracked
- Score: 0.35 avail + 0.25 comp + 0.20 lead + 0.20 price_norm
- WAL + busy_timeout; single-writer ingest during demo

6) Evolution
- Postgres; background ingest; ERP integrations; caching

