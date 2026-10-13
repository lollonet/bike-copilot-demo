---
id: ARCH-V2-09
domain: docs
status: draft
---

# 09 — Observability

> Logging strutturato, metriche, tracing, alerting.
> **VINCOLI FISSI** (costituzione architetturale): JSON structured logging e correlation ID sono obbligatori.

---

## Vincoli Non Negoziabili

Questi sono stabiliti dalla costituzione architetturale e **non sono oggetto di decisione**:

| Vincolo | Implementazione |
|---------|----------------|
| Logging strutturato **JSON** | Ogni log line è un oggetto JSON con campi standard |
| **Correlation ID** per request | Ogni HTTP request ha un UUID propagato in tutti i log |
| **Correlation ID** per scraping job | Ogni job ha un UUID propagato in tutti i log del job |
| **Correlation ID** per ordine | Ogni order_bundle ha un UUID per tracciare l'ottimizzazione |

La decisione riguarda **solo l'implementazione** (quale libreria, quale backend metriche, quale canale alert).

---

## Logging: structlog

| Criterio | structlog | loguru | pino |
|----------|----------|--------|------|
| Output JSON nativo | Sì (JSONRenderer) | Sì (serialize) | Sì (default) |
| Context binding | Eccellente (bound loggers) | Limitato | Eccellente |
| Async support | Sì | Sì | N/A (Node) |
| Integrazione FastAPI | Middleware standard | Middleware custom | N/A |
| Performance | Alta (processors pipeline) | Alta | N/A |
| Stdlib compatible | Sì (stdlib integration) | Sostituzione stdlib | N/A |

**Decisione**: `structlog` per Python. Motivazione: context binding eccellente (bound loggers per propagare correlation_id senza passarlo esplicitamente), output JSON nativo, integrazione stdlib per catturare log di librerie terze.

**loguru scartato**: API conveniente ma context binding meno potente. structlog permette di "legare" il correlation_id al logger una volta e averlo in tutti i log successivi senza passarlo come parametro.

**pino scartato**: Node.js (stack è Python).

### Formato Log

```json
{
  "timestamp": "2026-04-24T02:34:12.456Z",
  "level": "info",
  "event": "product_scraped",
  "correlation_id": "scrape-abc123",
  "supplier": "ciclopromo",
  "supplier_sku": "SHM-XT-M8100",
  "price": 45.90,
  "availability": "in_stock",
  "duration_ms": 234
}
```

### Propagazione Correlation ID

```
HTTP Request → FastAPI middleware genera request_id
    │
    ├─→ Search handler → log con request_id
    │
    ├─→ Optimizer → log con request_id
    │
    └─→ Scraping job (on-demand) → RQ job con correlation_id = request_id
         │
         ├─→ Login → log con correlation_id
         ├─→ Scrape page 1 → log con correlation_id
         └─→ Scrape page N → log con correlation_id
```

---

## Metriche: SQLite Metrics Table

| Criterio | Prometheus + Grafana | SQLite Metrics | File JSON rotato |
|----------|---------------------|----------------|-----------------|
| Footprint | 2 container (Prometheus + Grafana) | 0 container (SQLite file) | 0 container |
| Dashboard | Grafana (potente) | Query SQL + UI custom | Nessuna |
| Retention | Configurabile | Configurabile (DELETE WHERE) | File rotation |
| Complessità | Media (config, scrape targets) | Bassa | Bassa |

**Decisione**: SQLite file per metriche (separato dal DB principale PostgreSQL). Query dirette per dashboard minima nella webapp.

**Prometheus + Grafana scartato**: 2 container aggiuntivi, configurazione non banale, overkill per single-user con 3 scraping job/notte. Upgrade path per fase 2 se serve monitoring avanzato.

**File JSON rotato scartato**: non queryable, nessuna aggregazione nativa. SQLite offre SQL per query aggregate (media, count, percentile) senza overhead.

### Metriche Raccolte

| Metrica | Tipo | Granularità |
|---------|------|-------------|
| `scraping_duration_seconds` | Gauge | Per fornitore, per job |
| `scraping_items_total` | Counter | Per fornitore, per job |
| `scraping_errors_total` | Counter | Per fornitore, per job |
| `search_duration_ms` | Histogram | Per query |
| `optimizer_duration_ms` | Histogram | Per richiesta |
| `supplier_last_scraped_at` | Gauge | Per fornitore |

---

## Tracing: Log-based (Correlation ID + grep)

| Criterio | Jaeger | Log-based |
|----------|--------|-----------|
| Footprint | Container dedicato | Zero |
| Visualizzazione | UI trace waterfall | `grep correlation_id logs/*.json \| jq` |
| Complessità | Media (OpenTelemetry SDK) | Zero |

**Decisione**: tracing log-based con correlation ID. Per single-user con 3 servizi, `grep` + `jq` sui log JSON è sufficiente.

**Jaeger scartato**: container dedicato, OpenTelemetry SDK integration, overkill. Il valore del distributed tracing emerge con decine di microservizi, non con 3 container scraper + 1 webapp.

### Esempio Query Trace

```bash
# Tutti i log di un job di scraping
cat logs/scraper-ciclopromo.log | jq 'select(.correlation_id == "scrape-abc123")'

# Timeline di un job
cat logs/*.log | jq 'select(.correlation_id == "scrape-abc123")' | jq -s 'sort_by(.timestamp)'
```

---

## Alerting

| Canale | Quando | Come |
|--------|--------|------|
| **Telegram bot** | Scraping failure, stale data >48h | Bot Telegram con token in secrets |
| **Email** (fallback) | Se Telegram non configurato | SMTP locale o servizio esterno |
| **Log** (sempre) | Ogni evento | Strutturato JSON, sempre attivo |

### Alert Rules

| Alert | Condizione | Severità | Canale |
|-------|-----------|----------|--------|
| Scraping fallito | `scraping_job.status = 'failed'` e retry esauriti | Critical | Telegram |
| Dati stale | `supplier.last_scraped_at > 48h` | Warning | Telegram |
| Login fallito | 3 tentativi consecutivi falliti | Critical | Telegram |
| Rotation reminder | Credenziali non ruotate da 180 giorni | Info | Telegram |
| Disk space | Volume Docker > 80% | Warning | Telegram |

**Decisione**: Telegram come canale primario. Motivazione: gratuito, push notification su mobile, API semplice (HTTP POST), nessuna infrastruttura aggiuntiva.

**Slack scartato**: richiede workspace, overkill per single-user.
**PagerDuty/OpsGenie scartato**: servizi enterprise, costo non giustificato.

---

## Log Retention

| Log | Retention | Rotation |
|-----|-----------|----------|
| Scraping logs | 30 giorni | Rotazione giornaliera, compressione gzip |
| Application logs | 30 giorni | Rotazione giornaliera |
| Metrics SQLite | 90 giorni | DELETE WHERE timestamp < 90d (cron settimanale) |

Storage stimato: ~50 MB/giorno di log JSON (3 fornitori × catalogo completo) → ~1.5 GB/mese → gestibile su Mac Studio.

---

## Alternative Scartate

| Alternativa | Motivazione |
|-------------|-------------|
| **ELK Stack** | 3 container pesanti (Elasticsearch + Logstash + Kibana), GB di RAM. Per log di 3 scraper. |
| **Datadog/New Relic** | Cloud-only, costo mensile, viola self-hosted. |
| **Loki + Grafana** | Meglio di ELK ma comunque 2 container aggiuntivi per volume non giustificato. |

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Volume log per scraping intensivo | Disco pieno | Retention 30 giorni, compressione, alert disk space |
| SQLite metrics lock | Contention con scraping | Write-ahead log (WAL mode), writes in batch |
| Telegram bot token compromesso | Spam alerts | Token in sops, revocabile |

---

## Open Questions

1. **Retention policy**: 30 giorni sufficienti? → Rivalutare dopo 3 mesi di uso
2. **Soglie alerting per fornitore**: le soglie devono essere diverse per fornitore? → Probabilmente sì (RMS più lento)
3. **Dashboard metriche**: UI dedicata o sezione nella webapp? → Proposta: sezione nella webapp (s08)

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← s03** | Tech Stack | Python → structlog |
| **← s05** | Scraping Architecture | correlation_id per ogni job |
| **→ s11** | Deployment | Volume log, cron rotation, metriche |
| **← s09** | Secrets | Telegram bot token in sops |
