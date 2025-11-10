Bike Copilot Demo (Lite)

Goal: local demo to ingest parts lists from CSV (later PDF/web), normalize/dedup into SQLite, search with ranking, and generate quotes. This repo is structured to extend sources via provider adapters without reengineering the core.

Quick start
- Use `uv` for running and gates. If `uv` isn’t installed, follow https://docs.astral.sh/uv/ to install.

Makefile targets
- `make status` – ruff fix/format + basedpyright typecheck.
- `make test` – run pytest with correct env/cache.
- `make seed` – seed demo CSVs (o usare CLI synth per 1000 articoli).
- `make api` – run FastAPI on `:8000`.
- `make ui` – run Gradio UI on `:7860`.
- CLI help: `uv run python -m app.cli --help`.

Quick demo (2 minutes)
- `uv pip install -r requirements.txt`
- `cp .env.example .env` (opzionale: imposta VAT/auth)
- Popola dati:
  - semplice: `make seed`
  - catalogo reale + fornitori sintetici: `uv run python -m app.cli reset-db && uv run python -m app.cli ingest-csv-synth --csv ./catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml --suppliers 3 --coverage 0.65 --jitter 0.15`
- `make api` e in un’altra shell `make ui`
- UI: cerca (“borraccia”), aggiungi più offerte al carrello (Qtà +/−), crea preventivo (multi‑riga con totali). 
- API quick check:
  - Search: `curl -s :8000/search -H 'content-type: application/json' -d '{"query_text":"borraccia"}' | jq`
  - Facets: `curl -s :8000/facets -H 'content-type: application/json' -d '{"query_text":"borraccia"}' | jq`
  - Quote (multi‑item): `curl -s -u demo:demo123 :8000/quote -H 'content-type: application/json' -d '{"items":[{"offer_id":1,"qty":2},{"offer_id":2,"qty":1}],"customer_name":"Mario","customer_contact":"mario@example.com"}' | jq`

Environment
- Copy `.env.example` to `.env` e regola se serve.
- Variabili utili: `APP_DB_URL`, `APP_OUT_DIR`, `APP_VAT`, `APP_BASIC_USER`, `APP_BASIC_PASS`, `APP_API_BASE` (per UI → API).

Health
- `GET /health` → `{status:'ok', db:true, pdfkit:<bool>, version:'<x.y.z>'}`; responses include `X-Trace-Id` header.

CLI Autocomplete
- Show script: `uv run python -m app.cli --show-completion`
- Install: `uv run python -m app.cli --install-completion`
- After install, TAB completes commands/params; `--offer-id` dynamically completes from DB.

CLI Examples
- Ingest base CSV: `uv run python -m app.cli ingest-csv --products data/demo/products.csv --offers data/demo/offers.csv`
- Ingest CSV mappato: `uv run python -m app.cli ingest-csv-mapped --csv ./catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml`
- Ingest sintetico (doppioni per fornitori): `uv run python -m app.cli ingest-csv-synth --csv ./catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml --suppliers 3 --coverage 0.65 --jitter 0.15`
- Search: `uv run python -m app.cli search-cli --speed 11 --freehub HG`
- Quote (con qty): `uv run python -m app.cli quote-cli --offer-id <TAB> --qty 2 --customer-name Mario --customer-contact mario@example.com`
- UI: `uv run python -m app.cli ui`
- API: `uv run python -m app.cli api`

PDF Ingest
- Esempio: `uv run python -m app.ingest_pdf --pdf /path/to/catalog.pdf --mapping providers/example.yaml --provider ExamplePDF`
- Il mapping YAML definisce colonne → campi canonici.

Web Ingest (HTML mapping)
- Example: `uv run python -m app.cli fetch-web --html providers/html/example.html --mapping providers/web-example.yaml`
- Mapping YAML defines CSS selectors for `root`, `brand`, `mpn`, `name`, `price` (and optional `in_stock`, `lead_time_days`).

Web Ingest (remote pages)
- Fetch one or more URLs and upsert:
  - `uv run python -m app.cli fetch-web-url --url https://shop.example/cassettes?page=1 --mapping providers/web-example.yaml --follow-next --max-pages 3`
- Site search via URL template in mapping:
  - `uv run python -m app.cli search-web --query "catena 11v" --mapping providers/web-example.yaml`
- Mapping YAML extra keys:
  - `pagination.next`: CSS selector for the “next page” link
  - `search.url_template`: e.g. `https://shop.example/search?q={q}`
  - For auth/cookies: pass `--header "Cookie: a=b"` (permitted sites only)

WooCommerce example (Cicli Montanini)
- Mapping provided: `providers/web-ciclimontanini.yaml`
- Typical usage:
  - `uv run python -m app.cli search-web --query "catena 11v" --mapping providers/web-ciclimontanini.yaml --max-pages 2 --delay 1.0`
- Notes:
  - Listing pages often lack MPN; the adapter follows each product link and parses detail selectors (sku/price/stock) to ensure `brand+mpn` for dedupe.
  - Keep a small `--delay` and modest `--max-pages`; respect site TOS/robots. If blocked, pass a browser Cookie via `--header`.

Storeden example (Ciclodiffusione)
- Mapping provided: `providers/web-ciclodiffusione.yaml`
- Typical usage:
  - Search ingest: `uv run python -m app.cli search-web --query "catena" --mapping providers/web-ciclodiffusione.yaml --max-pages 2 --delay 1.0`
  - Sitemap ingest (if/when a product sitemap exists): `uv run python -m app.cli fetch-sitemap --sitemap https://www.ciclodiffusione.com/sitemap.xml --mapping providers/web-ciclodiffusione.yaml --contains /product/ --delay 0.8`
- Notes:
  - Listing pages contain name/price and link; detail pages expose OG meta (`og:title`, `og:description` for MPN/code, `og:price:amount`, `og:availability`). The adapter reads meta `content` attributes directly.
  - If the site restricts scraping or returns empty results, add a Cookie header: `--header "Cookie: <paste>"` and keep a reasonable `--delay`.

Security
- Basic Auth guards `/quote`, `/kpi/*`, and `/files/*` when `APP_BASIC_USER` and `APP_BASIC_PASS` are set.
- `/files/*` serves only `.html` and `.pdf` from `APP_OUT_DIR`.

UI features
- Ricerca per testo con token (brand/mpn/nome) + budget cap.
- Ricerca full‑width in alto; sotto, filtri primari: Categoria e Fornitori.
- Filtri dinamici post‑ricerca (facets): Velocità, Corpetto, Freno, Rotore, Axle.
- “Albero filtri”: dopo la prima ricerca compaiono radio per ciascun facet; scegli un valore per applicarlo al filtro.
- Gating intelligente: i "Filtri tecnici" si abilitano solo se coprono ≥15% dei risultati correnti, evitando filtri fuorvianti.
- “Solo in stock”, “Budget massimo” con info min/max da facets; campo numerico e slider sincronizzati (0 = nessun limite).
- Ricerca non parte ad ogni tasto: premi Invio nella casella di testo o il pulsante "Cerca"; i filtri invece aggiornano automaticamente i risultati.
- Carrello multi‑articolo con Qtà +/- , totali live (Subtotale/IVA/Totale).
- Preventivo multi‑riga con PDF/HTML; `file_url` se l’API è attiva; fallback locale robusto.

Quote customization
- Optional env: `APP_SHOP_NAME`, `APP_SHOP_ADDRESS`, `APP_SHOP_CONTACT`, `APP_SHOP_LOGO` (path/URL) for header in the PDF/HTML.

Systemd (example)
- Service file: `deploy/bike-copilot.service` (uses `EnvironmentFile=/etc/default/bike-copilot-demo`).
- Steps:
  1. `sudo mkdir -p /opt/bike-copilot-demo`
  2. `sudo rsync -a --exclude .venv ./ /opt/bike-copilot-demo/`
  3. `cd /opt/bike-copilot-demo && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && bash scripts/seed_demo.sh`
  4. `echo "APP_VAT=0.22" | sudo tee /etc/default/bike-copilot-demo`
  5. `sudo cp deploy/bike-copilot.service /etc/systemd/system/`
  6. `sudo systemctl daemon-reload && sudo systemctl enable --now bike-copilot.service`

Scheduled ingest
- `scripts/cron-ingest.sh` re-ingests CSVs; extend to PDFs as needed.

Directories
- `app/` – code (typed contracts, models, adapters, services).
- `data/demo/` – example CSVs.
- `scripts/` – install/seed helpers.
- `deploy/` – systemd example.

Notes
- Python runs via `uv run ...` in development.
- Boundaries use typed request/response models; no untyped dicts cross edges.
