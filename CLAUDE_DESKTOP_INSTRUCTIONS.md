# Bike Copilot - Istruzioni per Claude Desktop

## Panoramica Progetto

**Bike Copilot** è una piattaforma di aggregazione prezzi per ricambi bicicletta B2B. Permette ai negozi di biciclette di:
- Cercare ricambi per Part Number (PN), EAN, o nome prodotto
- Confrontare prezzi da più fornitori (dealer)
- Generare preventivi ottimizzati multi-dealer
- Gestire policy di spedizione e soglie minimo ordine

## Stack Tecnologico

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.12, FastAPI |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic v2 |
| Frontend | Gradio |
| Database | SQLite (dev), PostgreSQL (prod) |
| Package Manager | uv |
| Linting | ruff |
| Type Checking | basedpyright |
| Security Scan | bandit |
| Testing | pytest |

## Struttura Progetto

```
bike-copilot-demo/
├── app/                    # Codice applicativo
│   ├── adapters/           # Adapter per crawling (web, csv, pdf)
│   ├── api.py              # Endpoint FastAPI
│   ├── cli.py              # CLI Typer per crawl/ingest
│   ├── models.py           # Modelli SQLAlchemy
│   ├── search.py           # Logica di ricerca prodotti
│   ├── optimizer.py        # Ottimizzatore ordini multi-dealer
│   ├── quote.py            # Generazione preventivi PDF
│   ├── ui.py               # UI Gradio principale
│   └── ui_pn.py            # UI Gradio PN-first
├── providers/              # Configurazioni dealer (YAML)
│   ├── dealers.yaml        # Registry dealer
│   └── web-*.yaml          # Mapping per ogni dealer
├── docs/                   # Documentazione strutturata
│   ├── requirements/       # REQ-### requisiti funzionali
│   ├── architecture/       # ARC-### decisioni architetturali
│   └── technology/         # TECH-### scelte tecnologiche
├── scripts/                # Script CI (complexity, traceability)
├── tests/                  # Test pytest
├── traceability/           # Matrice tracciabilità requisiti
├── CONTROL.yaml            # Soglie qualità (complexity, coverage, KPI)
└── .github/workflows/      # CI/CD GitHub Actions
```

## CI/CD Pipeline

### Jobs Paralleli

| Job | Descrizione | Bloccante |
|-----|-------------|-----------|
| `lint-typecheck-test` | ruff + basedpyright + pytest | Si |
| `complexity` | Complexity gate (McCabe, Cognitive, LOC) | Parziale |
| `security` | Bandit security scan | Warning |
| `traceability` | Spec lint + matrice REQ tracciabilità | Si |

### Quality Gates (CONTROL.yaml)

```yaml
complexity:
  mccabe:    { warn: 8, fail: 12 }
  cognitive: { warn: 12, fail: 15 }
  func_loc:  { warn: 25, fail: 30 }

kpi:
  pn_match_precision: 0.995
  freshness_threshold_h: 24
```

### Comandi Quality Gate

```bash
# Lint
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/

# Type check
uv run basedpyright app/

# Tests
uv run pytest -v --tb=short tests/

# Security
uv run bandit -r app/ -ll -ii

# Complexity
uv run python scripts/complexity_gate.py --paths app scripts

# Traceability
uv run python scripts/spec_lint.py
uv run python scripts/traceability.py
```

### Claude Code Review (PR automatica)

Ogni PR riceve review automatica da Claude con:
- Check Python/FastAPI specifici
- Analisi SQLAlchemy 2.0 patterns
- Verifica security (path traversal, SQL injection)
- Trigger manuale: commenta `/claude-review`

## Modelli Dati Principali

### Product
```python
class Product(Base):
    brand: Mapped[str]      # es. "Shimano"
    mpn: Mapped[str]        # es. "CS-R8100"
    ean: Mapped[str | None] # EAN-13
    name: Mapped[str]       # Nome completo
    category: Mapped[str]   # es. "cassette"
```

### SupplierOffer
```python
class SupplierOffer(Base):
    product_id: Mapped[int]
    supplier: Mapped[str]       # Dealer key
    price: Mapped[float]
    in_stock: Mapped[bool]
    lead_time_days: Mapped[int]
    updated_at: Mapped[datetime]
```

## Comandi CLI Principali

```bash
# Crawl prodotti da un dealer
uv run python -m app.cli crawl <dealer_key> --limit 100

# Ingest dati nel database
uv run python -m app.cli ingest <dealer_key>

# Reset database per dealer
uv run python -m app.cli reset <dealer_key>

# Avvia UI Gradio
uv run python -m app.cli ui

# Avvia API FastAPI
uv run python -m app.cli api
```

## Convenzioni Codice

### SQLAlchemy 2.0 (OBBLIGATORIO)
```python
# CORRETTO
stmt = select(Product).where(Product.brand == "Shimano")
result = session.execute(stmt).scalars().all()

# SBAGLIATO (legacy API)
products = session.query(Product).filter_by(brand="Shimano").all()
```

### Session Management
```python
with SessionLocal() as session:
    # operazioni
    session.commit()
# auto-close garantito
```

### Type Hints
- Usa `Mapped[]` per SQLAlchemy
- Usa `| None` invece di `Optional[]`
- Evita `Any`, `cast`, `type: ignore`

### Error Handling
- Eccezioni custom in `app/exceptions.py`
- Log con `app/logging_utils.py`

## Requisiti Funzionali (REQ-###)

| ID | Descrizione |
|----|-------------|
| REQ-001 | Standard repository (docs, hooks, CI) |
| REQ-002 | UI con ricerca full-width e filtri dinamici |
| REQ-003 | Provider Ciclodiffusione (Storeden) |
| REQ-004 | Interfaccia PN-first e flusso preventivo |
| REQ-005 | Ottimizzatore ordine multi-dealer |
| REQ-006 | Branding preventivi |
| REQ-007 | Gestione dealer e policy spedizioni |
| REQ-008 | KPI freschezza e qualità dati |

## Commit Convention

Ogni commit DEVE avere prefisso REQ:
```
REQ-001: descrizione breve

Corpo opzionale con dettagli.
```

Hook pre-commit verifica automaticamente.

## Dealer Supportati

| Key | Nome | Piattaforma | Tipo |
|-----|------|-------------|------|
| rms | RMS | Custom SPA | web |
| ciclodiffusione | Ciclodiffusione | Storeden | web |
| cicli_montanini | Cicli Montanini | WooCommerce | web |

## Ottimizzatore Ordini

L'ottimizzatore (`app/optimizer.py`) minimizza il costo totale considerando:
- Prezzo prodotto per dealer
- Costi spedizione per dealer
- Soglie minimo ordine
- Disponibilità prodotti

## Note Importanti

- **Database**: SQLite in `data/bike.db`
- **Credenziali**: Mai committare, usa env vars (`DEALER_*`)
- **Crawling**: Rispetta rate limits
- **PDF**: Richiede wkhtmltopdf per preventivi
- **Tracciabilità**: Ogni file docs deve avere front-matter YAML valido
