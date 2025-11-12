---
id: ARC-010
domain: architecture
status: approved
source_of_truth: false
related: [ARC-INDEX, TECH-010]
---
Panoramica Architetturale

1) Contesto
Demo locale per acquisire liste fornitori (CSV ora; PDF/Web in seguito) in SQLite, cercare con ranking e generare preventivi. Bordi tipizzati chiari, un solo percorso per comportamento.

2) Componenti
- Ingest (adapter CSV/PDF/Web) → upsert idempotente
- Metacatalogo (SQLite, WAL): product, supplier_offer, event_log, raw_ingest, price_history
- Ricerca/Ranking: compatibilità + disponibilità/lead/prezzo
- API/UI/CLI: endpoint FastAPI; UI Gradio; CLI Typer con autocomplete
- Preventivo: Jinja2 HTML, PDF opzionale via wkhtmltopdf/pdfkit
- Ops: servizio systemd, artefatti out/, endpoint KPI

3) Modello dati (essenziale)
- product(id, brand, mpn, ean, name, speed, brake, axle, rotor, freehub, category)
- supplier_offer(id, product_id, supplier, price, in_stock, lead_time_days, updated_at, currency, extra)
- event_log(id, ts, type, payload)
- raw_ingest(id, ts, provider, kind, uri, content_hash, stored_path)
- price_history(id, ts, offer_id, price, source_hash)

4) Interfacce
- API: `/health`, `/search`, `/facets`, `/quote`, `/files/{name}`, `/kpi/today`
- CLI: `ingest-*`, `search-cli`, `quote-cli`, `ui`, `api`
- UI: Gradio Blocks; carrello + preventivi multi‑riga

5) Qualità
- Ingest idempotente; tracciamento variazioni prezzo
- Score: 0.35 avail + 0.25 comp + 0.20 lead + 0.20 price_norm
- WAL + busy_timeout; ingest a singolo writer durante la demo

6) Evoluzione
- Postgres; ingest in background; integrazioni ERP; cache
