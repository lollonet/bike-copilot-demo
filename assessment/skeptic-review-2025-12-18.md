# Skeptic Review Report - Bike Copilot Demo

**Data**: 2025-12-18
**Reviewer**: skeptic-reviewer agent
**Scope**: Full codebase analysis - bugs funzionali MEDIUM+

---

## Executive Summary

Analisi completa della codebase con focus su:
- Provider navigation e crawling
- Database structure e integrity
- Application logic
- Ingest pipeline
- API layer

**Risultato**: 14 bug funzionali identificati

| Severity | Count |
|----------|-------|
| CRITICAL | 1     |
| HIGH     | 5     |
| MEDIUM   | 8     |
| **TOTALE** | **14** |

---

## Bug Identificati

### BUG #1: Path Traversal in API /files/{name:path}
- **File**: `app/api.py:222-231`
- **Severity**: **CRITICAL**
- **Descrizione**: L'endpoint `/files/{name:path}` accetta percorsi arbitrari senza validare che il percorso risultante sia effettivamente dentro `settings.out_dir`. Un attaccante puo usare sequenze `../` per leggere file arbitrari sul filesystem.
- **Impatto**: Lettura di file sensibili (secrets, codice sorgente, database SQLite, .env). Full file disclosure vulnerability.
- **Riproduzione**: `GET /files/../../.env` oppure `GET /files/../../../etc/passwd`
- **Fix suggerito**: Verificare che il path risolto sia dentro `out_dir` usando `p.resolve().is_relative_to(Path(settings.out_dir).resolve())`.

```python
# Codice vulnerabile:
p = Path(settings.out_dir) / name
if not p.is_file() or p.suffix.lower() not in allowed:  # NON verifica traversal!
    raise HTTPException(status_code=404, detail="Not found")
```

---

### BUG #2: set.intersection TypeError quando per_pn_dealers e vuoto
- **File**: `app/optimizer.py:297-301`
- **Severity**: **HIGH**
- **Descrizione**: La funzione `_common_dealers` chiama `set.intersection(*per_pn_dealers)` quando `per_pn_dealers` potrebbe essere una lista vuota. `set.intersection()` senza argomenti solleva `TypeError: descriptor 'intersection' of 'set' object needs an argument`.
- **Impatto**: Crash dell'ottimizzatore quando un ordine ha zero righe valide (es. tutti i PN non trovati). L'API /optimize restituisce 500 Internal Server Error.
- **Riproduzione**: Chiamare `/optimize` con un elenco di `maker_pn` tutti non presenti nel database.
- **Fix suggerito**:
```python
def _common_dealers(per_pn: List[List[PNOfferItem]]) -> set[str]:
    per_pn_dealers: List[set[str]] = [
        set(o.dealer for o in offers) for offers in per_pn
    ]
    if not per_pn_dealers:  # FIX: check vuoto
        return set()
    return set.intersection(*per_pn_dealers)
```

---

### BUG #3: updated_at mai aggiornato durante upsert offerte
- **File**: `app/ingest.py:309-311`
- **Severity**: **HIGH**
- **Descrizione**: Quando un'offerta esistente viene aggiornata con nuovi valori di prezzo/stock/lead_time, il campo `updated_at` non viene modificato. Il timestamp rimane quello della creazione iniziale.
- **Impatto**: I KPI (`/kpi/summary`) calcolano percentuali di "updated_24h" errate. L'intero sistema di monitoraggio freshness dei dati e inaffidabile.
- **Riproduzione**: Ingerire lo stesso CSV due volte a distanza di 24 ore. Il campo `updated_at` rimane invariato.
- **Fix suggerito**:
```python
# In _update_offer_and_history, aggiungere:
offer_existing.updated_at = datetime.now(timezone.utc)
```

---

### BUG #4: _load_synonyms() crash se file non esiste
- **File**: `app/search.py:77-80`
- **Severity**: **HIGH**
- **Descrizione**: La funzione `_load_synonyms()` apre direttamente il file `settings.synonyms_path` senza gestire `FileNotFoundError`. Se il file non esiste, l'applicazione crasha.
- **Impatto**: Search e facets API restituiscono 500 se `app/synonyms.yaml` manca. Differisce da `_load_category_synonyms()` che gestisce correttamente il caso.
- **Riproduzione**: Eliminare o rinominare `app/synonyms.yaml`, poi chiamare `/search` o `/facets`.
- **Fix suggerito**:
```python
def _load_synonyms() -> dict[str, dict[str, list[str]]]:
    try:
        with open(settings.synonyms_path, "r", encoding="utf-8") as f:
            data: dict[str, dict[str, list[str]]] = yaml.safe_load(f) or {}
        return data
    except (OSError, FileNotFoundError):
        return {}
```

---

### BUG #5: Lambda closure bug in ingest-all-parallel
- **File**: `app/cli.py:994-1008`
- **Severity**: **HIGH**
- **Descrizione**: Le lambda definite nel loop di `tasks` catturano le variabili `cfg` e `session` per reference. Quando il loop termina, tutte le lambda puntano all'ultimo valore assegnato (ciclopromo/bikeparts), non ai rispettivi dealer.
- **Impatto**: Crawl parallelo fallisce o crawla il dealer sbagliato. Dati ingeriti sotto il fornitore errato, corruzione del database.
- **Riproduzione**: Eseguire `python -m app.cli ingest-all-parallel` e osservare che tutti i dealer usano la stessa configurazione.
- **Fix suggerito**: Usare argomenti di default per catturare il valore corrente:
```python
lambda cfg=cfg, session=session: _run_ciclodiffusione(...)
```
oppure usare `functools.partial`.

---

### BUG #6: Quote template path hardcoded
- **File**: `app/quote.py:40`
- **Severity**: **MEDIUM**
- **Descrizione**: Il percorso `"app/templates"` e hardcoded e funziona solo se il processo Python viene avviato dalla root del progetto.
- **Impatto**: Se l'API viene avviata da una directory diversa (es. `/var/www/` con symlink), la generazione quote fallisce con `TemplateNotFound`.
- **Riproduzione**: `cd /tmp && python -m app.cli api` poi chiamare `/quote`.
- **Fix suggerito**:
```python
templates_dir = Path(__file__).parent / "templates"
env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)))
```

---

### BUG #7: Ricorsione illimitata in sitemap parser
- **File**: `app/adapters/web_adapter.py:1075-1096`
- **Severity**: **MEDIUM**
- **Descrizione**: `_parse_sitemap_xml` si richiama ricorsivamente per ogni sitemap child senza limite di profondita. Un sitemap malevolo o ciclico causa stack overflow.
- **Impatto**: Denial of Service durante crawl. Il processo crasha con `RecursionError`.
- **Riproduzione**: Creare un sitemap XML che referenzia se stesso o chain di >1000 sitemap.
- **Fix suggerito**: Aggiungere parametro `depth` con limite massimo (es. 10), oppure passare a iterativo con stack esplicito.

---

### BUG #8: Race condition in upsert offer con begin_nested
- **File**: `app/ingest.py:254-274`
- **Severity**: **MEDIUM**
- **Descrizione**: Il pattern try/except IntegrityError con begin_nested non e atomico in SQLite con WAL. Due processi paralleli possono entrambi passare il check "offer not exists", poi uno fallisce con IntegrityError.
- **Impatto**: Durante `ingest-all-parallel`, offerte potrebbero essere skippate o duplicate. I contatori `offers_upserted` non sono accurati.
- **Riproduzione**: Eseguire due ingest paralleli sullo stesso dataset.
- **Fix suggerito**: Usare `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE` oppure un lock esplicito.

---

### BUG #9: _to_price solleva exception non gestita
- **File**: `app/adapters/web_adapter.py:119-135`
- **Severity**: **MEDIUM**
- **Descrizione**: `_to_price()` chiama `float(t)` senza try/except. Se il testo contiene caratteri non numerici residui (es. "N/A", "POA", "Chiama"), solleva `ValueError` non gestito.
- **Impatto**: Crawl di una singola pagina con prezzo invalido interrompe l'intero batch. Perdita di tutti i prodotti successivi nella pagina.
- **Riproduzione**: Crawlare una pagina con `<span class="price">Su richiesta</span>`.
- **Fix suggerito**:
```python
def _to_price(s: str) -> float:
    try:
        # ... parsing logic ...
        return float(t)
    except ValueError:
        return 0.0  # o raise un'exception specifica
```

---

### BUG #10: policy.py swap logic errato per base_cost
- **File**: `app/policy.py:93-98`
- **Severity**: **MEDIUM**
- **Descrizione**: La logica di swap quando `base >= free` assume che `ordered[1]` sia un costo di spedizione valido, ma potrebbe essere un altro threshold o un importo non correlato.
- **Impatto**: Estrazione policy sbagliata: il costo base spedizione potrebbe essere estratto come 49.00 (soglia) invece di 6.90 (costo reale).
- **Riproduzione**: HTML con "Spedizione gratuita oltre 49" e "Contributo ecologico 1". Il sistema potrebbe estrarre 1 come base_cost.
- **Fix suggerito**: Analizzare il contesto testuale per distinguere costi da soglie, non basarsi solo sull'ordinamento numerico.

---

### BUG #11: Soft-delete assente per offerte non piu presenti
- **File**: `app/ingest.py`
- **Severity**: **MEDIUM**
- **Descrizione**: L'ingest upserta offerte esistenti ma non marca come "removed" le offerte che non appaiono piu nel feed del fornitore. Se un prodotto viene rimosso dal catalogo del dealer, l'offerta resta attiva nel database.
- **Impatto**: Utenti vedono offerte fantasma non piu disponibili. Quote generate per prodotti non acquistabili.
- **Riproduzione**: Ingerire CSV con 100 offerte, poi reingerire CSV con 50 offerte (rimosse le altre 50). Le 50 rimosse restano in DB.
- **Fix suggerito**: Implementare reconciliation: marcare `in_stock=False` o `deleted_at` per offerte non viste nell'ultimo ingest.

---

### BUG #12: Browser leak in playwright_fetcher
- **File**: `app/adapters/playwright_fetcher.py:40-53`
- **Severity**: **MEDIUM**
- **Descrizione**: Se `page.goto()` o `page.fill()` sollevano un'eccezione, `browser.close()` non viene chiamato perche e fuori dal context manager.
- **Impatto**: Memory leak e processi Chromium orfani. Dopo molte chiamate fallite, il sistema esaurisce risorse.
- **Riproduzione**: Chiamare `fetch_rendered` su URL che causa timeout ripetutamente.
- **Fix suggerito**: Spostare `browser.close()` in un `finally` block o usare context manager.

---

### BUG #13: Division by zero in final_score
- **File**: `app/search.py:124-130`
- **Severity**: **MEDIUM**
- **Descrizione**: `price_norm = (min_price / offer.price)` puo causare division by zero se `offer.price == 0`. Il check `if offer.price and min_price` non protegge da `offer.price = 0.0` (truthy in Python e False, ma 0.0/qualcosa e valido).
- **Impatto**: Crash della ricerca se un'offerta ha prezzo 0.
- **Riproduzione**: Ingerire offerta con `price=0`, poi eseguire search.
- **Fix suggerito**:
```python
price_norm = (min_price / offer.price) if (offer.price and offer.price > 0 and min_price) else 0.5
```

---

### BUG #14: Walrus operator scope bug in parallel lambda
- **File**: `app/cli.py:1005-1006`
- **Severity**: **HIGH**
- **Descrizione**: L'espressione `if (cfg := cfgs.get("ciclodiffusione")) and (session := _build_session_for(...))` usa walrus operator dentro lambda. Le variabili `cfg` e `session` sono assegnate nello scope della lambda, ma la lambda e valutata in un thread diverso dopo che il loop principale e terminato.
- **Impatto**: La condizione `cfg := cfgs.get(...)` viene valutata al momento dell'esecuzione, non della definizione. Questo puo causare KeyError o uso del dealer sbagliato.
- **Riproduzione**: Osservare comportamento inconsistente durante `ingest-all-parallel`.
- **Fix suggerito**: Pre-calcolare cfg e session prima della lambda, passarli come argomenti bound.

---

## Raccomandazioni Prioritarie

### Immediate (Blockers)
1. **BUG #1**: Path traversal - vulnerabilita di sicurezza critica

### Urgent (Data Corruption Risk)
2. **BUG #5 + #14**: Lambda closure bugs - corruzione dati in produzione
3. **BUG #3**: updated_at refresh - KPI inaffidabili

### High Priority
4. **BUG #2**: set.intersection crash
5. **BUG #4**: synonyms.yaml FileNotFound

### Normal Priority
6. Tutti i bug MEDIUM (6-13)

---

## Metriche di Qualita Post-Fix Attese

Dopo aver risolto tutti i bug:
- Zero vulnerabilita di sicurezza note
- Ingest parallelo affidabile
- KPI freshness accurati
- Nessun crash su edge cases comuni
