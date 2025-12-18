# Copilot Prompt: Fix 14 Bug Funzionali

**Data**: 2025-12-18
**Riferimento**: `assessment/skeptic-review-2025-12-18.md`
**Mode**: SOTA (tutti i quality gates obbligatori)

---

## Istruzioni Generali

Sei incaricato di fixare 14 bug funzionali identificati nella codebase bike-copilot-demo. Procedi in ordine di priorita (CRITICAL > HIGH > MEDIUM). Per ogni fix:

1. Leggi il file indicato
2. Applica la patch minimale
3. Verifica che i test esistenti passino
4. Aggiungi test se il bug non era coperto

**Quality Gates obbligatori prima del commit:**
```bash
uv run ruff check app/
uv run ruff format --check app/
uv run basedpyright app/
uv run pytest -v --tb=short
```

---

## FASE 1: CRITICAL (Blockers)

### FIX #1: Path Traversal in /files/{path}

**File**: `app/api.py` (cerca endpoint `/files/`)

**Problema**: L'endpoint non valida path traversal con `../`

**Patch**:
```python
# PRIMA (vulnerabile):
@app.get("/files/{name:path}")
async def get_file(name: str) -> FileResponse:
    allowed = {".html", ".pdf"}
    p = Path(settings.out_dir) / name
    if not p.is_file() or p.suffix.lower() not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(p)

# DOPO (sicuro):
@app.get("/files/{name:path}")
async def get_file(name: str) -> FileResponse:
    allowed = {".html", ".pdf"}
    base_dir = Path(settings.out_dir).resolve()
    p = (base_dir / name).resolve()

    # Security: prevent path traversal
    if not p.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")

    if not p.is_file() or p.suffix.lower() not in allowed:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(p)
```

**Test da aggiungere** (in `tests/test_api.py`):
```python
def test_files_path_traversal_blocked(client):
    """Ensure path traversal attacks are blocked."""
    response = client.get("/files/../../.env")
    assert response.status_code == 403

    response = client.get("/files/../../../etc/passwd")
    assert response.status_code == 403
```

---

## FASE 2: HIGH Priority

### FIX #2: set.intersection() su lista vuota

**File**: `app/optimizer.py` (funzione `_common_dealers`)

**Patch**:
```python
# Trova la funzione _common_dealers e aggiungi check per lista vuota:
def _common_dealers(per_pn: list[list[PNOfferItem]]) -> set[str]:
    per_pn_dealers: list[set[str]] = [
        set(o.dealer for o in offers) for offers in per_pn
    ]
    if not per_pn_dealers:
        return set()
    return set.intersection(*per_pn_dealers)
```

---

### FIX #3: updated_at mai aggiornato

**File**: `app/ingest.py` (funzione che aggiorna offerte esistenti)

**Patch**: Cerca dove viene fatto l'update dell'offerta esistente e aggiungi:
```python
from datetime import datetime, timezone

# Nel blocco dove aggiorni offer_existing:
offer_existing.price = new_price
offer_existing.in_stock = new_stock
# ... altri campi ...
offer_existing.updated_at = datetime.now(timezone.utc)  # AGGIUNGI QUESTA RIGA
```

---

### FIX #4: _load_synonyms() FileNotFoundError

**File**: `app/search.py` (funzione `_load_synonyms`)

**Patch**:
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

### FIX #5 + #14: Lambda closure bug in ingest-all-parallel

**File**: `app/cli.py` (comando `ingest-all-parallel`, cerca `tasks = []` o lambda definitions)

**Problema**: Le lambda catturano variabili per reference, non per valore.

**Patch**: Usa `functools.partial` oppure default arguments:

```python
# OPZIONE A: Default arguments (piu semplice)
# PRIMA (buggy):
tasks.append(lambda: _run_ciclodiffusione(cfg, session))

# DOPO (corretto):
tasks.append(lambda cfg=cfg, session=session: _run_ciclodiffusione(cfg, session))

# OPZIONE B: functools.partial (piu esplicito)
from functools import partial
tasks.append(partial(_run_ciclodiffusione, cfg, session))
```

**Applica questo pattern a TUTTE le lambda nel loop di tasks.**

---

## FASE 3: MEDIUM Priority

### FIX #6: Template path hardcoded

**File**: `app/quote.py` (cerca `jinja2.Environment` o `"app/templates"`)

**Patch**:
```python
from pathlib import Path

# PRIMA:
env = jinja2.Environment(loader=jinja2.FileSystemLoader("app/templates"))

# DOPO:
templates_dir = Path(__file__).parent / "templates"
env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates_dir)))
```

---

### FIX #7: Ricorsione illimitata sitemap parser

**File**: `app/adapters/web_adapter.py` (funzione `_parse_sitemap_xml`)

**Patch**: Aggiungi parametro `depth` con limite:
```python
MAX_SITEMAP_DEPTH = 10

def _parse_sitemap_xml(url: str, headers: dict, depth: int = 0) -> list[str]:
    if depth > MAX_SITEMAP_DEPTH:
        log_warning("web_adapter", "sitemap", f"Max depth {MAX_SITEMAP_DEPTH} reached", {"url": url})
        return []

    # ... existing code ...

    # Nelle chiamate ricorsive, passa depth + 1:
    child_urls = _parse_sitemap_xml(child_sitemap_url, headers, depth + 1)
```

---

### FIX #8: Race condition in upsert

**File**: `app/ingest.py` (funzione di upsert offerte)

**Patch**: Usa `ON CONFLICT DO UPDATE` invece di try/except:
```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

stmt = sqlite_insert(SupplierOffer).values(
    product_id=product_id,
    supplier=supplier,
    price=price,
    in_stock=in_stock,
    updated_at=datetime.now(timezone.utc),
)
stmt = stmt.on_conflict_do_update(
    index_elements=["product_id", "supplier"],
    set_={
        "price": stmt.excluded.price,
        "in_stock": stmt.excluded.in_stock,
        "updated_at": stmt.excluded.updated_at,
    }
)
session.execute(stmt)
```

---

### FIX #9: _to_price() ValueError non gestito

**File**: `app/adapters/web_adapter.py` (funzione `_to_price`)

**Patch**:
```python
def _to_price(s: str) -> float:
    """Parse price string to float, return 0.0 on failure."""
    if not s:
        return 0.0
    try:
        # Remove currency symbols, spaces, thousands separators
        t = s.strip()
        t = re.sub(r"[^\d,.]", "", t)
        # Handle European format (1.234,56) vs US format (1,234.56)
        if "," in t and "." in t:
            if t.rfind(",") > t.rfind("."):
                t = t.replace(".", "").replace(",", ".")
            else:
                t = t.replace(",", "")
        elif "," in t:
            t = t.replace(",", ".")
        return float(t) if t else 0.0
    except (ValueError, AttributeError):
        return 0.0
```

---

### FIX #10: policy.py swap logic

**File**: `app/policy.py` (cerca logica di swap per base_cost/free_threshold)

**Patch**: Questo richiede analisi del contesto testuale. Per ora, aggiungi logging per debug:
```python
# Aggiungi logging per capire cosa viene estratto:
log_debug("policy", "extraction", "Extracted values", {
    "base_cost": base_cost,
    "free_threshold": free_threshold,
    "raw_text": raw_text[:200]
})

# Poi implementa euristica basata su keyword:
# - Se il numero appare vicino a "spedizione", "shipping", "costo" -> e un costo
# - Se il numero appare vicino a "gratuita", "free", "oltre", "sopra" -> e una soglia
```

---

### FIX #11: Soft-delete offerte mancanti

**File**: `app/ingest.py`

**Patch**: Implementa reconciliation al termine dell'ingest per un provider:
```python
def reconcile_offers(session: Session, supplier: str, seen_product_ids: set[int]) -> int:
    """Mark offers not seen in this ingest as out of stock."""
    stmt = (
        update(SupplierOffer)
        .where(
            SupplierOffer.supplier == supplier,
            SupplierOffer.in_stock == True,
            SupplierOffer.product_id.notin_(seen_product_ids)
        )
        .values(in_stock=False, updated_at=datetime.now(timezone.utc))
    )
    result = session.execute(stmt)
    session.commit()
    return result.rowcount
```

Chiama questa funzione alla fine di ogni ingest per un provider specifico.

---

### FIX #12: Browser leak in playwright_fetcher

**File**: `app/adapters/playwright_fetcher.py`

**Patch**: Usa try/finally o context manager:
```python
async def fetch_rendered(url: str, ...) -> str:
    browser = None
    try:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        return content
    finally:
        if browser:
            await browser.close()
```

---

### FIX #13: Division by zero in search

**File**: `app/search.py` (cerca `price_norm` o divisione per `offer.price`)

**Patch**:
```python
# PRIMA:
price_norm = (min_price / offer.price) if offer.price and min_price else 0.5

# DOPO:
price_norm = (min_price / offer.price) if (offer.price and offer.price > 0 and min_price) else 0.5
```

---

## Checklist Finale

Dopo aver applicato tutti i fix:

- [ ] FIX #1: Path traversal (CRITICAL)
- [ ] FIX #2: set.intersection vuoto (HIGH)
- [ ] FIX #3: updated_at refresh (HIGH)
- [ ] FIX #4: synonyms FileNotFound (HIGH)
- [ ] FIX #5+14: Lambda closure (HIGH)
- [ ] FIX #6: Template path (MEDIUM)
- [ ] FIX #7: Sitemap recursion limit (MEDIUM)
- [ ] FIX #8: Race condition upsert (MEDIUM)
- [ ] FIX #9: _to_price ValueError (MEDIUM)
- [ ] FIX #10: Policy swap logic (MEDIUM)
- [ ] FIX #11: Soft-delete reconciliation (MEDIUM)
- [ ] FIX #12: Browser leak (MEDIUM)
- [ ] FIX #13: Division by zero (MEDIUM)

**Quality Gates:**
```bash
uv run ruff check app/
uv run ruff format app/
uv run basedpyright app/
uv run pytest -v --tb=short
```

**Commit message suggerito:**
```
fix: resolve 14 functional bugs from skeptic review

CRITICAL:
- CVE-like: path traversal in /files/{path} endpoint

HIGH:
- set.intersection crash on empty list
- updated_at never refreshed on upsert
- synonyms.yaml FileNotFoundError crash
- lambda closure bug in parallel ingest

MEDIUM:
- template path hardcoded
- unlimited sitemap recursion
- race condition in offer upsert
- _to_price unhandled ValueError
- policy extraction swap logic
- missing soft-delete reconciliation
- playwright browser leak
- division by zero in search scoring

Refs: assessment/skeptic-review-2025-12-18.md
```
