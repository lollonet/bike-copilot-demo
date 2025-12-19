# 🚴 Bike Copilot — Unified B2B Bicycle Parts Platform

## 🎯 Project SSOT (Single Source of Truth)
The project documentation has been refactored for AI-driven development. Please refer to these core files:
- **[VISION.md](./VISION.md)**: Project goals, target users, and scope.
- **[REQ.md](./REQ.md)**: Functional requirements and user stories.
- **[ARCH.md](./ARCH.md)**: Data model, software components, and system architecture.
- **[TECH.md](./TECH.md)**: Technology stack, coding standards, and AI constraints.

---

## 🚀 Quick Start

### Prerequisites
```bash
# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/yourusername/bike-copilot-demo
cd bike-copilot-demo
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your dealer credentials
```

### Essential Commands
```bash
make status     # Run all quality checks (lint, format, type)
make test       # Execute test suite with coverage
make api        # Start FastAPI server (port 8000)
make ui-pn      # Launch PN-first UI (port 7861)
make crawl      # Dealer sync (alias web-crawl: Montanini + Ciclodiffusione)
make all-dealers-crawl  # Crawl tutti i dealer via seed URL (RMS/CicloPromo richiedono credenziali)
make ingest-all # Seed CSV demo + crawl di tutti i dealer + reconcile
make reconcile-offers  # Marca stale le offerte non aggiornate nell’ultima run
make reset-db   # Resetta il DB SQLite locale e ricrea le tabelle
make fetch-rendered URL=...  # Playwright fetch per pagine JS/login (extra opzionale)
```

## 🏗️ System Components

### 1. Dealer Management System (REQ-007)
Centralized configuration for multi-dealer operations:

```yaml
# providers/dealers.yaml
dealers:
  - key: ciclopromo
    platform: custom-cartzilla
    mapping: providers/web-ciclopromo.yaml
    auth:
      mode_env: DEALER_CICLOPROMO_AUTH_MODE
    login:
      mode: form
      url: https://shop.ciclopromo.com/login
      preflight_url: https://shop.ciclopromo.com
```

**Sync Command**:
```bash
# Synchronize dealer catalog and policies
uv run python -m app.cli dealer-sync ciclopromo --mode all

# Supported modes:
# - policy: Extract shipping policies only
# - catalogo: Ingest product catalog
# - all: Both policy and catalog
```

### 2. Multi-Source Ingestion

#### Web Scraping (with Authentication)
```bash
# Direct URL with session management
uv run python -m app.cli fetch-web-url \
  --url "https://dealer.com/products" \
  --mapping providers/web-dealer.yaml \
  --follow-next --max-pages 10 \
  --header "Cookie: session=xyz"

# Search-based ingestion
uv run python -m app.cli search-web \
  --query "shimano 11 speed" \
  --mapping providers/web-dealer.yaml
```

#### CSV Import with Synthetic Suppliers
```bash
# Real catalog with synthetic competition
uv run python -m app.cli ingest-csv-synth \
  --csv catalogo_real_mtb.csv \
  --mapping providers/csv-catalogo-mtb.yaml \
  --suppliers 5 \
  --coverage 0.7 \
  --jitter 0.15
```

#### PDF Extraction
```bash
uv run python -m app.cli ingest-pdf \
  --pdf catalog.pdf \
  --mapping providers/pdf-mapping.yaml
```

### 3. PN-First Search & Optimization

#### Batch PN Search API
```python
POST /search_pn_batch
{
  "pns": ["CN-HG601", "CS-HG800", "FD-R7000"],
  "filters": {
    "in_stock": true,
    "max_price": 500
  }
}
```

#### Multi-Scenario Order Optimizer
```python
POST /optimize
{
  "items": [
    {"maker_pn": "EB400441", "qty": 1, "locked_dealer": "Ciclodiffusione"},
    {"maker_pn": "RM421691201", "qty": 2}
  ],
  "params": {
    "scenario": "miglior-prezzo",   # oppure: un-solo-dealer | max-n-dealer | piu-veloce
    "max_dealer": 2,
    "penale_dealer": 3.5,
    "penale_lead": 0.5
  }
}

Response
{
  "lines": [
    {
      "offer_id": 12,
      "maker_pn": "EB400441",
      "dealer": "Ciclodiffusione",
      "unit_price": 20.0,
      "qty": 1,
      "line_total": 20.0,
      "lead_time_days": null
    },
    ...
  ],
  "dealers": ["Ciclodiffusione"],
  "costs": {
    "subtotal": 34.0,
    "shipping": 6.9,
    "penalties": 0.0,
    "total": 40.9
  },
  "notes": [
    "Scenario miglior-prezzo: selezionati i prezzi minimi per ciascun PN indipendentemente dal dealer."
  ],
  "ts": "2025-11-15T09:00:00Z"
}
```

### 4. KPI & Monitoring Dashboard

```bash
# Real-time metrics
GET /kpi/summary

Response:
{
  "pn_coverage": 0.87,      # 87% PNs have offers
  "freshness_24h": 0.65,     # 65% updated < 24h ago
  "avg_lag_hours": 3.2,      # Avg update delay
  "unmapped_pns": ["..."],   # PNs needing attention
  "dealer_health": {
    "ciclopromo": {"last_sync": "2024-01-15T10:30:00Z", "status": "healthy"},
    "ciclodiffusione": {"last_sync": "2024-01-15T09:00:00Z", "status": "degraded"}
  }
}
```

## 📸 Screenshots (da aggiornare)
- UI Search (desktop): `docs/screenshots/ui-search.png`
- Risultati + facet chips: `docs/screenshots/ui-results.png`
- Preventivo PDF/HTML: `docs/screenshots/ui-quote.png`

Rigenera gli screenshot lanciando l’UI (`make ui`) e usando uno strumento di cattura; salva nei path sopra per tenerli versionati.

## 🎬 Scenario Demo (miglior-prezzo)
1. `make seed` per popolare il DB locale con catalogo demo.
2. `make api` e in altro terminale `make ui` (o `make ui-pn` per la variante PN-first).
3. Cerca ad es. “freno” con budget 80€ e in-stock attivo.
4. Applica facet (categoria, fornitore) e usa i chip “Filtri attivi” per rimuoverli rapidamente.
5. Seleziona un’offerta, genera preventivo; verifica `out/QUOTE-*.html`/`.pdf`.

## 🌐 Web crawl & Playwright (JS/login)
- `make web-crawl Q="sella casco"`: esegue crawl Montanini + Ciclodiffusione con query fornite.
- CLI Playwright (opzionale, richiede `pip install playwright && playwright install chromium`):
  ```bash
  uv run python -m app.cli fetch-rendered --url https://example.com/prod --wait-ms 2000
  # Login form
  uv run python -m app.cli fetch-rendered --url https://example.com/area \
      --login-url https://example.com/login --username user --password pass \
      --user-selector '#email' --pass-selector '#pwd' --submit-selector 'button[type=submit]'
  ```

## 🔐 Security Architecture

### Multi-Layer Authentication
1. **Basic Auth**: Protects `/quote`, `/kpi/*`, `/files/*`
2. **Cookie Auth**: Session-based dealer authentication
3. **Form Auth**: POST/GET login with CSRF protection
4. **API Keys**: Per-dealer credentials in environment

### Environment Configuration
```bash
# .env (never commit!)
APP_BASIC_USER=admin
APP_BASIC_PASS=secure-password

# Dealer credentials
DEALER_CICLOPROMO_AUTH_MODE=form
DEALER_CICLOPROMO_USERNAME=b2b-user
DEALER_CICLOPROMO_PASSWORD=b2b-pass

DEALER_CICLODIFFUSIONE_AUTH_MODE=cookie
DEALER_CICLODIFFUSIONE_COOKIE=session=xyz123
```

## 🧪 Testing & Quality

### Test Coverage
```bash
# Run full test suite
make test

# Specific test categories
pytest tests/test_dealers.py -v         # Dealer management
pytest tests/test_web_adapter.py -v     # Web scraping
pytest tests/test_optimization.py -v    # Order optimizer
```

### Quality Gates (REQ-001)
```bash
# Pre-commit checks
make lint       # Ruff linting
make format     # Black formatting
make typecheck  # Pyright/Basedpyright
make complexity # Cyclomatic complexity < 10
```

## 📊 Database Schema

```sql
-- Core entities
Products (id, brand, mpn, name, category)
SupplierOffers (id, product_id, supplier, price, in_stock, lead_time_days)
PNMapping (dealer, dealer_pn_norm, maker_pn_norm, confidence)
DealerPolicy (dealer, base_cost, free_threshold, lead_days_std)
EventLog (type, payload, created_at)  -- Audit trail
```

## 🚢 Production Deployment

### Systemd Service
```bash
# Install service
sudo cp deploy/bike-copilot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bike-copilot

# Monitor logs
journalctl -u bike-copilot -f
```

### Docker Deployment (Alternative)
```bash
docker build -t bike-copilot .
docker run -d \
  --name bike-copilot \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  -v bike-copilot-db:/app/data \
  bike-copilot
```

## 🔄 Continuous Integration

### GitHub Actions Pipeline
```yaml
# .github/workflows/ci.yml
- Quality checks (lint, format, type)
- Test suite with coverage
- Security scanning (Bandit, Safety)
- Docker build and push
- Deployment to staging
```

## 📈 Performance Metrics

- **Ingestion Rate**: ~1000 products/minute (web scraping)
- **Search Latency**: < 50ms for PN lookup (indexed)
- **Optimization Time**: < 200ms for 100-item orders
- **Database Size**: ~100MB for 50K products × 5 suppliers

## 🛠️ Advanced CLI Usage

### Autocomplete Setup
```bash
# Enable shell completion
uv run python -m app.cli --install-completion

# Now use TAB for suggestions
uv run python -m app.cli dealer-sync <TAB>
# Shows: ciclopromo, ciclodiffusione, rms, bikeparts
```

### Batch Operations
```bash
# Process multiple dealers
for dealer in ciclopromo ciclodiffusione rms; do
  uv run python -m app.cli dealer-sync $dealer --mode all
done

# Schedule with cron
0 */6 * * * cd /opt/bike-copilot && .venv/bin/python -m app.cli dealer-sync --all
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feat/amazing-feature`
3. Follow conventions: `REQ-XXX: Clear commit message`
4. Ensure tests pass: `make test`
5. Submit PR with comprehensive description

## 📝 License

Proprietary - All rights reserved

## 🆘 Support

- Issues: GitHub Issues
- Documentation: `/docs` folder
- Runbooks: `/docs/standards/RUNBOOKS/`

---

Built with ❤️ using FastAPI, SQLAlchemy, Pydantic, and UV
