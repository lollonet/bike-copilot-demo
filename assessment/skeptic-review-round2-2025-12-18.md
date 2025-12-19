# Skeptic Review Report - Round 2

**Data**: 2025-12-18
**Reviewer**: skeptic-reviewer agent
**Scope**: Secondo pass - bug NUOVI non coperti dal round 1

---

## Executive Summary

Secondo pass di analisi focalizzato su:
- File non esaminati a fondo nel round 1 (ui.py, ui_pn.py, types.py)
- Categorie di bug non coperte (SSRF, DoS, memory exhaustion)
- Pattern architetturali problematici

**Risultato**: 11 nuovi bug funzionali identificati

| Severity | Count |
|----------|-------|
| HIGH     | 5     |
| MEDIUM   | 6     |
| **TOTALE** | **11** |

---

## Bug Identificati

### NEW BUG #15: N+1 Query + Memory Exhaustion in kpi_summary
- **File**: `app/api.py:524-546`
- **Severity**: **HIGH**
- **Descrizione**: La funzione `_count_unmapped_pn` carica TUTTE le offerte con `extra IS NOT NULL` in memoria, poi esegue una query separata per OGNI offerta.
```python
candidates = db.scalars(
    select(SupplierOffer).where(SupplierOffer.extra.isnot(None))
).all()  # Carica tutto in memoria
...
for offer in candidates:
    exists = db.scalar(...)  # N query per N offerte!
```
- **Impatto**: Con 100k offerte, esegue 100k query separate + carica tutto in RAM. DoS garantito.
- **Fix suggerito**: Usare una LEFT JOIN o subquery per contare in una sola query.

---

### NEW BUG #16: File Write Race Condition in quote.py
- **File**: `app/quote.py:31-36`
- **Severity**: **HIGH**
- **Descrizione**: Due quote create nello stesso secondo sovrascrivono lo stesso file.
```python
ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
base = f"QUOTE-{ts}"  # Stesso nome se stesso secondo!
```
- **Impatto**: Quote perse, clienti che ricevono preventivi errati.
- **Fix suggerito**: Aggiungere microseconds o UUID al nome file: `f"QUOTE-{ts}-{uuid.uuid4().hex[:8]}"`

---

### NEW BUG #17: Gradio State Mutation Bug
- **File**: `app/ui.py:1243-1246`
- **Severity**: **MEDIUM**
- **Descrizione**: Lo stato Gradio viene mutato in-place invece di creare nuove istanze.
```python
def _on_add(..., cart: dict[int, dict[str, Any]]):
    prev = cart.get(offer_id, {**info, "qty": 0})
    prev.update({"qty": ...})
    cart[offer_id] = prev  # Mutazione in-place del dict passato!
```
- **Impatto**: Comportamenti imprevedibili nella UI, stato inconsistente tra componenti.
- **Fix suggerito**: Creare sempre un nuovo dict: `new_cart = {**cart}; new_cart[offer_id] = {...}`

---

### NEW BUG #18: OverflowError non catturato in _safe_int
- **File**: `app/ui_pn.py:111-117`
- **Severity**: **MEDIUM**
- **Descrizione**: `int(float("inf"))` solleva `OverflowError`, non catturato.
```python
def _safe_int(value: Any, default: int | None) -> int | None:
    try:
        return int(value)  # OverflowError se value=float("inf")!
    except (TypeError, ValueError):  # OverflowError non catturato
        return default
```
- **Impatto**: Crash della UI se l'utente inserisce valori speciali.
- **Fix suggerito**: Aggiungere `OverflowError` alla tupla delle eccezioni.

---

### NEW BUG #19: Session/Client Leak in _build_dealer_session
- **File**: `app/cli.py:1449-1464`
- **Severity**: **MEDIUM**
- **Descrizione**: Se le funzioni di autenticazione sollevano eccezioni, il client HTTP non viene chiuso.
```python
def _build_dealer_session(cfg: DealerConfig) -> DealerSession:
    client = _build_http_client()  # Creato qui
    if mode == "cookie":
        _apply_cookie_auth(client, cfg, cookie)  # Puo sollevare typer.BadParameter!
    # Se eccezione, client non chiuso -> resource leak
    return DealerSession(client, cfg.login)
```
- **Impatto**: Memory leak e connessioni aperte accumulate.
- **Fix suggerito**: Wrappare in try/except e chiudere client in caso di errore.

---

### NEW BUG #20: DoS via Unbounded Sitemap URL Count
- **File**: `app/cli.py:576-577`
- **Severity**: **HIGH**
- **Descrizione**: Con `limit=0`, tutti gli URL del sitemap vengono scaricati.
```python
limit: int = typer.Option(0, help="max URLs to visit (0 = no limit)")
...
urls = parse_sitemap_urls(sitemap, headers=headers, limit=(limit or None))
```
- **Impatto**: Un sitemap con milioni di URL causa memory exhaustion e richieste infinite.
- **Fix suggerito**: Impostare un limite massimo ragionevole (e.g., 10000) anche quando limit=0.

---

### NEW BUG #21: Full Table Scan Memory Exhaustion in Search
- **File**: `app/search.py:136` e `app/pn.py:70,140`
- **Severity**: **HIGH**
- **Descrizione**: Carica TUTTI i prodotti con TUTTE le offerte in memoria.
```python
products = db.scalars(
    select(Product).options(selectinload(Product.offers))
).all()  # Nessun limite!
```
- **Impatto**: Con 100k prodotti e 10 offerte ciascuno = 1M oggetti in RAM. OOM e DoS.
- **Fix suggerito**: Aggiungere paginazione o usare filtri SQL prima di caricare.

---

### NEW BUG #22: Global Cache Race Condition
- **File**: `app/search.py:15,37-57`
- **Severity**: **MEDIUM**
- **Descrizione**: Cache globale senza protezione thread-safe.
```python
_category_synonyms_cache: dict[str, str] = {}  # Globale!

def _load_category_synonyms() -> dict[str, str]:
    global _category_synonyms_cache
    if _category_synonyms_cache:  # Check...
        return _category_synonyms_cache
    # ...then set (non atomico)
    _category_synonyms_cache = _build_category_synonym_mapping(raw)
```
- **Impatto**: In server multi-worker, race condition tra check e set. Dati corrotti o eccezioni.
- **Fix suggerito**: Usare `threading.Lock()` o `functools.lru_cache`.

---

### NEW BUG #23: min() su Sequenza Vuota in _build_search_items
- **File**: `app/search.py:235-237`
- **Severity**: **MEDIUM**
- **Descrizione**: Se tutti i prezzi sono `None`, `min()` fallisce.
```python
min_price = min(
    o.price for (o, ...) in offers if o.price is not None
)  # ValueError se generatore vuoto!
```
- **Impatto**: Crash dell'endpoint `/search` se tutti i risultati hanno prezzo nullo.
- **Fix suggerito**: Usare `min(..., default=0.0)` o controllare prima.

---

### NEW BUG #24: SSRF in CLI fetch commands
- **File**: `app/cli.py:497-518`
- **Severity**: **HIGH**
- **Descrizione**: URL arbitrari dall'utente passati direttamente a httpx senza validazione.
```python
@app.command("fetch-web-url")
def fetch_web_url(
    url: list[str] = typer.Option(...),  # User input!
):
    ...
    fetch_and_parse_urls(urls, ...)  # Nessuna validazione URL!
```
- **Impatto**: Accesso a risorse interne (localhost, cloud metadata endpoint 169.254.169.254).
- **Fix suggerito**: Validare che gli URL siano HTTPS e non puntino a IP privati/localhost.

---

### NEW BUG #25: Integer Overflow in line_total (optimizer.py)
- **File**: `app/optimizer.py:227,236-237`
- **Severity**: **MEDIUM**
- **Descrizione**: Moltiplicazione di prezzi/quantita grandi senza controllo overflow.
```python
unit = float(o.price or 0.0)
lines.append(OptimizeLine(
    line_total=unit * q,  # Se unit=1e308 e q=2, risulta inf
))
```
- **Impatto**: Calcoli errati di costi/totali, preventivi con importi `inf`.
- **Fix suggerito**: Validare che price sia entro bounds ragionevoli (e.g., < 1e9).

---

## Riepilogo Cumulativo (Round 1 + Round 2)

| Severity | Round 1 | Round 2 | Totale |
|----------|---------|---------|--------|
| CRITICAL | 1 | 0 | **1** |
| HIGH | 5 | 5 | **10** |
| MEDIUM | 8 | 6 | **14** |
| **TOTALE** | **14** | **11** | **25** |

---

## Raccomandazioni Prioritarie Round 2

### Immediate (DoS/Security)
1. **BUG #20**: Unbounded sitemap URLs - DoS
2. **BUG #21**: Full table scan - Memory exhaustion
3. **BUG #24**: SSRF in fetch commands

### High Priority (Data Integrity)
4. **BUG #15**: N+1 query in KPI
5. **BUG #16**: Quote file race condition

### Normal Priority
6. Tutti i bug MEDIUM (17-19, 22-23, 25)
