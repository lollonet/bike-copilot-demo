---
id: REBOOT-05
domain: docs
status: draft
---

# 05 — Execution Roadmap

## Dependency Graph

```
T0 (env) → T1 (housekeeping) → T2 (credentials)
                                      │
                                   ◆ GATE: login OK?
                                      │
                                T3 (scraping smoke)
                                      │
                                   ◆ GATE: parser OK?
                                      │
                                T4 (data + search)
                                      │
                                T5 (optimizer + quote)
                                      │
                                T6 (demo walkthrough)
```

Ogni GATE blocca il flusso. Se fallisce, debug/fix prima di proseguire. Il tempo di fix e' coperto dal contingency buffer (8h base).

---

## Mini-Triad Sequence

### T0 — Environment Validation
**Pre-requisito**: nessuno
**Azioni**:
1. `python3 --version` (verificare >=3.10)
2. `uv sync` (sincronizzare dipendenze)
3. `playwright install chromium` (browser per scraping)
4. `uv run pytest --co -q` (verificare che i test si raccolgono)
5. `uv run ruff check app/` + `uv run basedpyright app/` (sanity check)

**Effort**: 1h / 2h / 4h
**Exit criteria**: `uv run pytest -v` → 199 collected, 0 errors
**Prova del budino**: `make status` passa senza errori

---

### T1 — Housekeeping (commit, merge, tag)
**Pre-requisito**: T0 completato
**Azioni**:
1. `git stash` (o `git commit`) i changes su fix/log-002 (web_adapter.py, test_fetch_timeout.py)
2. `git checkout main`
3. Merge PR #85 → `gh pr merge 85 --merge`
4. Merge PR #86 → `gh pr merge 86 --merge`
5. Merge PR #87 → `gh pr merge 87 --merge`
6. `git pull origin main`
7. `uv run pytest -v` (re-test post-merge — DEVE passare)
8. Tornare su fix/log-002: `git checkout fix/log-002-trace-id-propagation`
9. `git rebase main` (incorporare le 3 PR mergiate)
10. Applicare stashed/committed changes se necessario
11. `uv run pytest -v` (re-test post-rebase)
12. Merge PR #88 → push + `gh pr merge 88 --merge`
13. `git checkout main && git pull`
14. `git tag v0-pre-reboot` (baseline per rollback)

**Effort**: 2h / 4h / 8h
**Exit criteria**: main ha tutti i fix security/logging, tag v0-pre-reboot creato, 199 test passano
**Prova del budino**: `git log --oneline -5 main` mostra i merge delle 4 PR

---

### T2 — Credential Check + Login Test
**Pre-requisito**: T1 completato (main aggiornato)
**Azioni**:
1. Verificare `.env` — controllare che le variabili per ogni fornitore siano presenti
2. Per ogni fornitore (RMS, Ciclopromo, Ciclodiffusione):
   - Tentare login manuale sul portale web nel browser (verificare che le credenziali funzionino)
   - Se scadute: rinnovare le credenziali sul sito del fornitore
   - Aggiornare `.env` con nuove credenziali
3. Testare login automatico: `uv run python -m app.cli fetch-web-url <test_url_fornitore>`
4. Se Playwright fallisce (anti-bot, DOM cambiato): debug e fix

**Effort**: 2h / 6h / 12h

**◆ GATE**: almeno 2/3 fornitori con login funzionante. Se 0/3: STOP, rivalutare approccio.

**Exit criteria**: login automatico funziona su almeno 2 fornitori
**Prova del budino**: comando fetch-web-url ritorna HTML con dati prodotto (non pagina di login)

---

### T3 — Scraping Smoke Test
**Pre-requisito**: T2 completato (login funzionante)
**Azioni**:
1. `make reset-db` (wipare dati demo, partire puliti)
2. Per ogni fornitore con login OK:
   - `make crawl-<fornitore>` (o equivalente con 1-2 pagine)
   - Verificare che i prodotti vengano parsati correttamente
   - Controllare: brand, mpn, prezzo, disponibilita' estratti
3. Se selettori CSS rotti: aggiornare `providers/mappings/<fornitore>_mapping.yaml`
4. `uv run python -m app.cli ingest-csv-mapped` o equivalente per verificare ingest

**Effort**: 2h / 4h / 8h

**◆ GATE**: almeno 10 prodotti reali nel DB per almeno 2 fornitori. Se 0: STOP, fix parser.

**Exit criteria**: `SELECT count(*) FROM product` > 10, `SELECT count(*) FROM supplier_offer` > 10
**Prova del budino**: `curl localhost:8000/dealers` mostra fornitori con offerte > 0

---

### T4 — Data Ingest + Search Test
**Pre-requisito**: T3 completato (dati reali nel DB)
**Azioni**:
1. Fix BIZ-001: aggiungere `default=1.0` a `min()` in `app/search.py:247`
2. `make api` (avviare FastAPI)
3. Testare search con query reali del negozio:
   - `curl -X POST localhost:8000/search -d '{"query_text":"shimano deore"}'`
   - `curl -X POST localhost:8000/search_pn -d '{"maker_pn":"CN-HG601"}'`
4. Verificare che i risultati contengano prodotti reali con prezzi e disponibilita'
5. Testare facets: `curl -X POST localhost:8000/facets -d '{}'`

**Effort**: 2h / 4h / 8h
**Exit criteria**: search ritorna prodotti reali con prezzi, PN search trova corrispondenze
**Prova del budino**: risposta JSON con items[].price > 0 e items[].supplier non vuoto

---

### T5 — Optimizer + Quote Test
**Pre-requisito**: T4 completato (search funzionante con dati reali)
**Azioni**:
1. Comporre carrello con 5-10 ricambi reali (PN che servono davvero al negozio)
2. Testare tutti e 4 gli scenari:
   - `curl -X POST localhost:8000/optimize -d '{"items":[...], "params":{"scenario":"miglior-prezzo"}}'`
   - Ripetere per un-solo-dealer, max-n-dealer, piu-veloce
3. Verificare che l'ottimizzazione produca risultati sensati (prezzi ragionevoli, dealer reali)
4. Generare preventivo: `curl -X POST localhost:8000/quote -H "Authorization: Basic ..." -d '{"items":[...],"customer_name":"Test","customer_contact":"test"}'`
5. Aprire il file HTML generato e verificare layout

**Effort**: 2h / 4h / 6h
**Exit criteria**: optimizer ritorna risultati per tutti i 4 scenari, preventivo HTML leggibile
**Prova del budino**: file HTML in `out/` con tabella prezzi per dealer

---

### T6 — Demo Walkthrough End-to-End
**Pre-requisito**: T5 completato
**Azioni**:
1. `make ui-pn` (avviare UI PN-first su port 7861)
2. Workflow completo nel browser:
   - Cercare un ricambio reale
   - Visualizzare offerte da piu' fornitori
   - Aggiungere al carrello
   - Lanciare ottimizzazione
   - Generare preventivo
3. Ripetere per 3 scenari diversi (ricambi diversi)
4. Documentare eventuali problemi UX da fixare post-MVP
5. Se tutto funziona: **MVP VALIDATO**

**Effort**: 2h / 3h / 4h
**Exit criteria**: 3 scenari completati end-to-end senza errori bloccanti
**Prova del budino**: 3 preventivi HTML generati con dati reali del negozio

---

## Budget Totale

| Step | Best | Base | Worst |
|------|------|------|-------|
| T0 env | 1h | 2h | 4h |
| T1 housekeeping | 2h | 4h | 8h |
| T2 credentials | 2h | 6h | 12h |
| T3 scraping | 2h | 4h | 8h |
| T4 search | 2h | 4h | 8h |
| T5 optimizer+quote | 2h | 4h | 6h |
| T6 demo | 2h | 3h | 4h |
| Contingency (gate fix) | — | 8h | 12h |
| **TOTALE** | **13h** | **35h** | **62h** |
