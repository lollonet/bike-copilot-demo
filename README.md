Bike Copilot Demo — PN‑first (Italia)

Obiettivo: demo locale per acquisire liste ricambi da CSV (in seguito PDF/web), normalizzare/deduplicare in SQLite, cercare con ranking e generare preventivi. Il repository è strutturato per estendere le fonti tramite adapter dei provider senza riscrivere il core.

Mappa Documenti (in italiano)
- Visione: `VISION.md` (radice)
- Architettura: `ARCH.md` (radice) e `docs/architecture/ARC-010-overview.md`
  - Wireframe UX PN‑first: `docs/architecture/ARC-020-ux-wireframes.md`
- Tecnologia: `TECH.md` (radice) e `docs/technology/TECH-010-runtime.md`
- Requisiti: `docs/requirements/REQ-INDEX.md` (include REQ‑004..008)
- Runbook: `docs/standards/RUNBOOKS/` (07..11 per PN‑first)

Avvio rapido
- Usa `uv` per esecuzione e gate. Se `uv` non è installato, segui le istruzioni su https://docs.astral.sh/uv/.

Target Makefile
- `make status` – ruff fix/format + basedpyright typecheck.
- `make test` – esegue pytest con env/cache corretti.
- `make seed` – popola CSV demo (oppure CLI synth per 1000 articoli).
- `make api` – avvia FastAPI su `:8000`.
- `make ui` – avvia Gradio UI su `:7860`.
- Aiuto CLI: `uv run python -m app.cli --help`.

Demo rapida (2 minuti)
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

Ambiente
- Copia `.env.example` in `.env` e regola se serve.
- Variabili utili: `APP_DB_URL`, `APP_OUT_DIR`, `APP_VAT`, `APP_BASIC_USER`, `APP_BASIC_PASS`, `APP_API_BASE` (per UI → API).

Health
- `GET /health` → `{status:'ok', db:true, pdfkit:<bool>, version:'<x.y.z>'}`; le risposte includono l’header `X-Trace-Id`.

Autocomplete CLI
- Mostra script: `uv run python -m app.cli --show-completion`
- Installa: `uv run python -m app.cli --install-completion`
- Dopo l’installazione, TAB completa comandi/parametri; `--offer-id` completa dinamicamente dal DB.

Esempi CLI
- Ingest CSV mappato: `uv run python -m app.cli ingest-csv-mapped --csv ./catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml`
- Ingest sintetico (doppioni per fornitori): `uv run python -m app.cli ingest-csv-synth --csv ./catalogo_real_mtb.csv --mapping providers/csv-catalogo-mtb.yaml --suppliers 3 --coverage 0.65 --jitter 0.15`
- Ricerca: `uv run python -m app.cli search-cli --speed 11 --freehub HG`
- Preventivo (con quantità): `uv run python -m app.cli quote-cli --offer-id <TAB> --qty 2 --customer-name Mario --customer-contact mario@example.com`
- UI: `uv run python -m app.cli ui`
- API: `uv run python -m app.cli api`

Ingest PDF
- Esempio: `uv run python -m app.ingest_pdf --pdf /path/to/catalog.pdf --mapping providers/example.yaml --provider ExamplePDF`
- Il mapping YAML definisce colonne → campi canonici.

Web Ingest (mapping HTML)
- Esempio: `uv run python -m app.cli fetch-web --html providers/html/example.html --mapping providers/web-example.yaml`
- Il mapping YAML definisce i selettori CSS per `root`, `brand`, `mpn`, `name`, `price` (ed eventualmente `in_stock`, `lead_time_days`).

Web Ingest (pagine remote)
- Recupera una o più URL e upsert:
  - `uv run python -m app.cli fetch-web-url --url https://shop.example/cassettes?page=1 --mapping providers/web-example.yaml --follow-next --max-pages 3`
- Ricerca sito via template URL nel mapping:
  - `uv run python -m app.cli search-web --query "catena 11v" --mapping providers/web-example.yaml`
- Chiavi extra del mapping YAML:
  - `pagination.next`: selettore CSS per il link “pagina successiva”
  - `search.url_template`: es. `https://shop.example/search?q={q}`
  - Per auth/cookie: passa `--header "Cookie: a=b"` (solo siti consentiti)

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

UI (stato attuale)
- Ricerca testuale con filtri dinamici e carrello multi‑articolo (in transizione verso PN‑first).
- Preventivo multi‑riga con PDF/HTML; branding opzionale via variabili ambiente.
Nota: stiamo migrando a PN‑first (vedi REQ‑004..006). I comandi esistenti restano per compatibilità demo.

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
- `scripts/` – install/seed helpers.
- `deploy/` – systemd example.

Notes
- Python runs via `uv run ...` in development.
- Boundaries use typed request/response models; no untyped dicts cross edges.
