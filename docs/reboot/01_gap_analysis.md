---
id: REBOOT-01
domain: docs
status: draft
---

# 01 — Gap Analysis vs MVP Target

## Classi di Prova

| Classe | Significato | Azione richiesta |
|--------|-------------|------------------|
| **P0** | Blocked by external dependency — non verificabile senza azione esterna | Test manuale obbligatorio |
| **P1** | Synthetic-only — testato con fixture, mai con dati reali | Test con dati reali |
| **P2** | Previously-validated — funzionava mesi fa, stato attuale sconosciuto | Ri-verifica |
| **P3** | Locally-reproducible-now — verificabile subito con comando concreto | Pronto |

Asse **freshness**: stale (>3 mesi) / unknown / recent (<1 mese).

---

## Criterio 1: Login B2B Reale

| Aspetto | Stato | Classe | Freshness | Evidenza |
|---------|-------|--------|-----------|----------|
| Codice login | EXISTS | P2 | stale | `app/cli_helpers/service_helpers.py:278` (form), `:381` (SPA) |
| Playwright fetcher | EXISTS | P2 | stale | `app/adapters/playwright_fetcher.py:40-57` |
| Credenziali .env | EXISTS | **P0** | **stale** | `.env` presente ma credenziali mesi fa — **possibilmente scadute** |
| Config fornitori | EXISTS | P2 | stale | `providers/dealers.yaml` — 4 fornitori configurati |

**Gap**: Le credenziali B2B potrebbero essere scadute. I portali fornitori potrebbero aver cambiato form di login, DOM, anti-bot.

| Severity | Effort best/base/worst |
|----------|----------------------|
| **blocker-MVP** | 2h / 6h / 12h |

**Verifica manuale**: `uv run python -m app.cli fetch-web-url <dealer_url>` per ogni fornitore, oppure test Playwright diretto.

---

## Criterio 2: Search Ricambi

| Aspetto | Stato | Classe | Freshness | Evidenza |
|---------|-------|--------|-----------|----------|
| API endpoint | EXISTS | P1 | recent | `app/api.py:122` — `POST /search` |
| Search engine | EXISTS | P1 | recent | `app/search.py:228` — scoring, filtering |
| PN search | EXISTS | P1 | recent | `app/pn.py:57` — `search_pn()` |
| Test unitari | PASS | P1 | recent | `tests/test_search.py` — 5 test, tutti passano |
| Dati reali | **MISSING** | — | — | DB ha solo dati sintetici/demo |

**Gap**: Search funziona su fixture ma mai testata con catalogo reale da fornitori. Il full-table-scan (issue #91) e' accettabile con <10k prodotti demo.

| Severity | Effort best/base/worst |
|----------|----------------------|
| **polish** (dipende da criterio 1 per dati reali) | 1h / 2h / 4h |

**Verifica manuale**: dopo ingest dati reali, `curl -X POST localhost:8000/search -d '{"query_text":"shimano deore"}'`.

---

## Criterio 3: Optimizer 4 Scenari

| Aspetto | Stato | Classe | Freshness | Evidenza |
|---------|-------|--------|-----------|----------|
| API endpoint | EXISTS | P1 | recent | `app/api.py:225` — `POST /optimize` |
| miglior-prezzo | EXISTS | P1 | recent | `app/optimizer.py:216-239` |
| un-solo-dealer | EXISTS | P1 | recent | `app/optimizer.py:268-293` |
| max-n-dealer | EXISTS | P1 | recent | `app/optimizer.py:346-362` |
| piu-veloce | EXISTS | P1 | recent | `app/optimizer.py:242-265` |
| Shipping policy | EXISTS | P1 | recent | `app/optimizer.py:89-97`, default `(6.9, 49.0)` |
| Test unitari | PASS | P1 | recent | `tests/test_optimizer.py` — 5 test, tutti passano |

**Gap**: Greedy heuristic (non ILP). Accettabile per demo. Non testato con dati reali multi-fornitore.

| Severity | Effort best/base/worst |
|----------|----------------------|
| **polish** (dipende da criterio 1+2 per dati reali) | 1h / 2h / 4h |

**Verifica manuale**: `curl -X POST localhost:8000/optimize -d '{"items":[{"maker_pn":"CN-HG601","qty":2}]}'`.

---

## Criterio 4: Preventivo PDF/HTML

| Aspetto | Stato | Classe | Freshness | Evidenza |
|---------|-------|--------|-----------|----------|
| API endpoint | EXISTS | P1 | recent | `app/api.py:295` — `POST /quote` (auth required) |
| HTML generation | EXISTS | P2 | stale | `app/quote.py:39-57`, `app/templates/quote.html` |
| PDF generation | **MISSING** | P0 | — | `wkhtmltopdf` non installato (`which wkhtmltopdf` → exit 1) |
| Fallback HTML | EXISTS | P3 | recent | `app/quote.py:60-69` — graceful fallback se wkhtmltopdf assente |
| Test | PASS | P1 | recent | `tests/test_quote_render.py` |

**Gap**: PDF richiede installazione `wkhtmltopdf`. HTML funziona come fallback.

| Severity | Effort best/base/worst |
|----------|----------------------|
| **polish** (HTML funziona, PDF e' nice-to-have) | 1h / 2h / 4h |

**Verifica manuale**: `brew install wkhtmltopdf` poi test via API.

---

## Criterio 5: No-Submit (by design)

| Aspetto | Stato | Classe | Freshness | Evidenza |
|---------|-------|--------|-----------|----------|
| Nessun codice di submit | **P3** | P3 | recent | Nessun endpoint/funzione di submit ordine nel codebase |

**Gap**: Nessuno. Il sistema genera preventivi, non submita ordini. L'utente copia manualmente.

| Severity | Effort |
|----------|--------|
| **nessuno** | 0h |

---

## Riepilogo Gap

| Criterio | Stato | Classe | Severity | Effort (base) |
|----------|-------|--------|----------|---------------|
| Login B2B | P0 (blocked) | blocker-MVP | **blocker** | 6h |
| Search | P1 (synthetic) | polish | polish | 2h |
| Optimizer | P1 (synthetic) | polish | polish | 2h |
| Preventivo | P2/P0 (HTML ok, PDF missing) | polish | polish | 2h |
| No-submit | P3 (by design) | nessuno | — | 0h |

**Unico blocker**: credenziali + login reale sui fornitori.
