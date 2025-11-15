---
id: TECH-010
domain: technology
status: approved
source_of_truth: false
related: [TECH-INDEX, ARC-010]
---
Runtime e Ambiente

Stack
- API/UI/CLI: FastAPI, Gradio, Typer; Python via uv
- Typi/lint/format: Pydantic v2, basedpyright, ruff
- DB: SQLite (WAL), SQLAlchemy 2.x
- ETL: pandas, pdfplumber (PDF), BeautifulSoup/httpx (web)
- Templating/PDF: Jinja2 + wkhtmltopdf/pdfkit (fallback HTML se assente)

Schema DB
- L’istanza SQLite unica (`app.db`) ospita i domini prodotti/offerte e i log di ingest; la figura seguente riassume colonne chiave e relazioni FK.

```mermaid
erDiagram
    Product {
        integer id PK
        string brand
        string mpn
        string name
        string ean
        string category
    }
    SupplierOffer {
        integer id PK
        integer product_id FK
        string supplier
        float price
        bool in_stock
        integer lead_time_days
    }
    PriceHistory {
        integer id PK
        integer offer_id FK
        float price
        datetime ts
    }
    PNMapping {
        integer id PK
        integer product_id FK
        string dealer
        string maker_pn_norm
        string dealer_pn_norm
    }
    DealerPolicy {
        integer id PK
        string dealer
        float base_cost
        float free_threshold
        integer lead_days_std
    }
    EventLog {
        integer id PK
        datetime ts
        string type
        json payload
    }
    RawIngest {
        integer id PK
        datetime ts
        string provider
        string kind
        string uri
        string content_hash
    }
    Product ||--o{ SupplierOffer : "offers"
    Product ||--o{ PNMapping : "maker PN"
    SupplierOffer ||--o{ PriceHistory : "changes"
```

Boundary e Contratti
- Tutti i bordi esterni usano modelli tipizzati (vedi app/types.py). Nessun dict non tipizzato attraversa i bordi.
- L’ingest usa adapter provider che emettono ProductInput/OfferInput; l’upsert è idempotente e traccia lo storico prezzi.

Operatività
- Script: `make status`, `make test`, `make api`, `make ui`
- CI: vedi ARC-001 e workflow CI per l’ordine dei gate
- Systemd: deploy/bike-copilot.service; env tramite `/etc/default/bike-copilot-demo`

Configurazione (env)
- APP_DB_URL, APP_OUT_DIR, APP_PREFER_IN_STOCK, APP_SYNONYMS,
  APP_BASIC_USER/APP_BASIC_PASS, APP_VAT

Evidenze
- Conservare note di audit della `.venv` nella storia di TECH.md o nei session summary quando necessario.
