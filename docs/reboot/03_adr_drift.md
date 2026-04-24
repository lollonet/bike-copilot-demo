---
id: REBOOT-03
domain: docs
status: draft
---

# 03 — ADR/REQ Drift Check

## ADR Compliance

| ADR | Decisione | Stato Codice | Verdict |
|-----|-----------|-------------|---------|
| ADR-001 (SQLite) | SQLite come DB primario per deploy locale | **CONFORME** — `app/models.py:42-43` WAL mode, `app/config.py:17-20` `sqlite:///` default | OK |
| ADR-002 (HTMX) | Jinja2 + HTMX per UI | **VIOLATO** — UI implementata con Gradio (`app/ui.py:5`, `app/ui_pn.py:5`). Zero HTMX nel codebase. Jinja2 usata solo per template quote (`app/quote.py:8`) | Eccezione candidata |
| ADR-003 (Playwright) | Playwright per scraping con httpx fallback | **CONFORME** — `app/adapters/playwright_fetcher.py` (lazy loading), `app/adapters/web_adapter.py` (httpx fallback) | OK |

### ADR-002: Eccezione Candidata (Gradio vs HTMX)

**Fatto**: Il codice usa Gradio per entrambe le UI (main port 7860, PN-first port 7861). HTMX non e' presente in nessun file del repository.

**Criteri per ratificare l'eccezione**:
- Gradio e' sufficiente per demo single-user? **Si** — funziona, test passano
- Gradio limita il MVP? **No** — i 5 criteri MVP sono soddisfacibili con Gradio
- Migrare a HTMX ora costerebbe quanto? **Molto** — 722 LOC di UI da riscrivere

**Conseguenze della ratifica**:
- Future stime di effort basate su Gradio, non HTMX
- docs/decisions/ADR-002-htmx.md va aggiornato con nota "superseded by Gradio"
- L'architettura docs/architecture/07_ui_architecture.md (che descrive HTMX) non e' implementata

**Decisione**: NON pre-ratificata qui. L'utente decidera' dopo aver letto questo documento. Per il MVP, Gradio funziona.

---

## REQ Implementation Status

| REQ | Titolo | Stato | Classe | Evidenza |
|-----|--------|-------|--------|----------|
| REQ-001 | Product Search | **Implementato** | P1 | `app/search.py:228`, `POST /search` (`app/api.py:122`), `tests/test_search.py` (5 test) |
| REQ-002 | Offers Display | **Parziale** | P1 | UI mostra offerte in Gradio (`app/ui_handlers_search.py`). Manca endpoint dedicato `GET /products/{id}/offers` citato nel REQ |
| REQ-003 | Order Optimizer | **Implementato** | P1 | `app/optimizer.py:164-172` (4 scenari), `POST /optimize` (`app/api.py:225`), `tests/test_optimizer.py` (5 test) |
| REQ-004 | Cart Management | **Implementato** | P1 | `app/ui_handlers_cart.py` (add/remove/adjust/clear), `tests/test_ui_handlers_cart.py` (15 test) |
| REQ-005 | Quote Generation | **Implementato** | P2 | `app/quote.py:22-28`, `POST /quote` (`app/api.py:295`), `tests/test_quote_render.py` |
| REQ-006 | Dealer Configuration | **Implementato** | P1 | `app/dealers.py`, `providers/dealers.yaml`, `GET /dealers` (`app/api.py:191`), `tests/test_dealers.py` (7 test) |
| REQ-007 | Data Crawling | **Implementato** | P0 | `app/adapters/web_adapter.py`, `app/commands/ingest_commands.py`, `Makefile:crawl-*`. P0 perche' dipende da credenziali + fornitori esterni |
| REQ-008 | Quality KPIs | **Implementato** | P1 | `app/api.py:433,455` — `GET /kpi/today`, `GET /kpi/summary`, `tests/test_api.py` |

### REQ-002 Gap Detail
Il REQ specifica un endpoint `GET /products/{id}/offers` per visualizzare le offerte di un singolo prodotto. L'implementazione attuale mostra le offerte nella UI Gradio come risultati di ricerca (search → lista offerte), non come endpoint dedicato. Per il MVP demo, la funzionalita' e' coperta dalla UI search. L'endpoint dedicato e' un **polish post-MVP**.
