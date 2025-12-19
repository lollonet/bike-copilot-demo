# Copilot Prompt: Fix 11 Bug Funzionali (Round 2)

**Data**: 2025-12-18
**Riferimento**: `assessment/skeptic-review-round2-2025-12-18.md`
**Mode**: SOTA (tutti i quality gates obbligatori)
**Prerequisito**: Completare prima i fix del Round 1

---

## Istruzioni Generali

Sei incaricato di fixare 11 bug funzionali identificati nel SECONDO pass di review. Procedi in ordine di priorita (HIGH > MEDIUM). Per ogni fix:

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

## FASE 1: HIGH Priority (DoS/Security)

### FIX #15: N+1 Query + Memory Exhaustion in kpi_summary

**File**: `app/api.py` (cerca `_count_unmapped_pn` o `kpi_summary`)

**Problema**: Carica tutte le offerte in memoria, poi esegue N query separate.

**Patch**:
```python
# PRIMA (N+1 query):
def _count_unmapped_pn(db: Session) -> int:
    candidates = db.scalars(
        select(SupplierOffer).where(SupplierOffer.extra.isnot(None))
    ).all()
    count = 0
    for offer in candidates:
        exists = db.scalar(
            select(func.count()).select_from(PNMapping).where(...)
        )
        if not exists:
            count += 1
    return count

# DOPO (single query con LEFT JOIN):
def _count_unmapped_pn(db: Session) -> int:
    """Count offers with extra data but no PN mapping."""
    subq = (
        select(PNMapping.supplier, PNMapping.supplier_pn)
        .distinct()
        .subquery()
    )
    stmt = (
        select(func.count())
        .select_from(SupplierOffer)
        .outerjoin(
            subq,
            and_(
                SupplierOffer.supplier == subq.c.supplier,
                # Assumendo che supplier_pn sia in extra JSON
                func.json_extract(SupplierOffer.extra, "$.pn") == subq.c.supplier_pn
            )
        )
        .where(
            SupplierOffer.extra.isnot(None),
            subq.c.supplier.is_(None)  # No mapping exists
        )
    )
    return db.scalar(stmt) or 0
```

---

### FIX #16: File Write Race Condition in quote.py

**File**: `app/quote.py` (cerca generazione nome file con timestamp)

**Problema**: Due quote nello stesso secondo sovrascrivono lo stesso file.

**Patch**:
```python
import uuid
from datetime import datetime, timezone

# PRIMA:
ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
base = f"QUOTE-{ts}"

# DOPO:
ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
unique_id = uuid.uuid4().hex[:8]
base = f"QUOTE-{ts}-{unique_id}"
```

---

### FIX #20: DoS via Unbounded Sitemap URL Count

**File**: `app/cli.py` (comando `fetch-sitemap`, cerca `limit: int`)

**Problema**: `limit=0` significa nessun limite, rischio DoS.

**Patch**:
```python
MAX_SITEMAP_URLS = 50000  # Limite massimo ragionevole

@app.command("fetch-sitemap")
def fetch_sitemap(
    ...
    limit: int = typer.Option(0, help="max URLs to visit (0 = use default max)"),
):
    # Applica limite massimo
    effective_limit = limit if 0 < limit <= MAX_SITEMAP_URLS else MAX_SITEMAP_URLS
    urls = parse_sitemap_urls(sitemap, headers=headers, limit=effective_limit)

    if len(urls) >= effective_limit:
        log_warning("cli", "sitemap", f"URL count capped at {effective_limit}")
```

---

### FIX #21: Full Table Scan Memory Exhaustion in Search

**File**: `app/search.py` (cerca `select(Product).options(selectinload`)

**Problema**: Carica tutti i prodotti senza limite.

**Patch**:
```python
MAX_SEARCH_RESULTS = 1000

def search_products(db: Session, query: str, ...) -> list[SearchResult]:
    # Applica filtri SQL PRIMA di caricare
    stmt = (
        select(Product)
        .options(selectinload(Product.offers))
        .where(...)  # Filtri di ricerca
        .limit(MAX_SEARCH_RESULTS)  # AGGIUNGI LIMITE
    )
    products = db.scalars(stmt).all()
```

**Applica lo stesso pattern anche in `app/pn.py` se presente.**

---

### FIX #24: SSRF in CLI fetch commands

**File**: `app/cli.py` (comando `fetch-web-url`)

**Problema**: URL arbitrari senza validazione.

**Patch**:
```python
import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"}
BLOCKED_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.",
                    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                    "172.30.", "172.31.", "192.168.")

def _validate_url(url: str) -> bool:
    """Validate URL is safe (no SSRF)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname or ""
        if host in BLOCKED_HOSTS:
            return False
        if any(host.startswith(p) for p in BLOCKED_PREFIXES):
            return False
        # Check if it's an IP and if it's private
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except ValueError:
            pass  # Not an IP, hostname is OK
        return True
    except Exception:
        return False

@app.command("fetch-web-url")
def fetch_web_url(url: list[str] = typer.Option(...)):
    # Valida tutti gli URL prima di procedere
    for u in url:
        if not _validate_url(u):
            raise typer.BadParameter(f"URL not allowed (security): {u}")
    # ... rest of function
```

---

## FASE 2: MEDIUM Priority

### FIX #17: Gradio State Mutation Bug

**File**: `app/ui.py` (cerca `_on_add` o funzioni che modificano `cart`)

**Problema**: Mutazione in-place dello stato.

**Patch**:
```python
# PRIMA (mutazione in-place):
def _on_add(..., cart: dict[int, dict[str, Any]]):
    prev = cart.get(offer_id, {**info, "qty": 0})
    prev.update({"qty": new_qty})
    cart[offer_id] = prev
    return cart

# DOPO (nuova istanza):
def _on_add(..., cart: dict[int, dict[str, Any]]):
    new_cart = dict(cart)  # Shallow copy
    prev = new_cart.get(offer_id, {**info, "qty": 0})
    new_cart[offer_id] = {**prev, "qty": new_qty}  # Nuovo dict
    return new_cart
```

---

### FIX #18: OverflowError non catturato in _safe_int

**File**: `app/ui_pn.py` (funzione `_safe_int`)

**Patch**:
```python
# PRIMA:
def _safe_int(value: Any, default: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

# DOPO:
def _safe_int(value: Any, default: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):  # Aggiunto OverflowError
        return default
```

---

### FIX #19: Session/Client Leak in _build_dealer_session

**File**: `app/cli.py` (funzione `_build_dealer_session`)

**Patch**:
```python
def _build_dealer_session(cfg: DealerConfig) -> DealerSession:
    client = _build_http_client()
    try:
        if mode == "cookie":
            _apply_cookie_auth(client, cfg, cookie)
        elif mode == "basic":
            _apply_basic_auth(client, cfg)
        return DealerSession(client, cfg.login)
    except Exception:
        client.close()  # Cleanup on error
        raise
```

---

### FIX #22: Global Cache Race Condition

**File**: `app/search.py` (cerca `_category_synonyms_cache`)

**Patch**:
```python
from functools import lru_cache

# PRIMA (globale non thread-safe):
_category_synonyms_cache: dict[str, str] = {}

def _load_category_synonyms() -> dict[str, str]:
    global _category_synonyms_cache
    if _category_synonyms_cache:
        return _category_synonyms_cache
    ...

# DOPO (lru_cache thread-safe):
@lru_cache(maxsize=1)
def _load_category_synonyms() -> dict[str, str]:
    """Load category synonyms (cached, thread-safe)."""
    try:
        with open(settings.category_synonyms_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, FileNotFoundError):
        return {}
    return _build_category_synonym_mapping(raw)

# Rimuovi la variabile globale _category_synonyms_cache
```

---

### FIX #23: min() su Sequenza Vuota

**File**: `app/search.py` (cerca `min_price = min(`)

**Patch**:
```python
# PRIMA:
min_price = min(
    o.price for (o, ...) in offers if o.price is not None
)

# DOPO:
prices = [o.price for (o, ...) in offers if o.price is not None and o.price > 0]
min_price = min(prices, default=0.0)
```

---

### FIX #25: Integer Overflow in line_total

**File**: `app/optimizer.py` (cerca `line_total=unit * q`)

**Patch**:
```python
MAX_REASONABLE_PRICE = 1_000_000_000  # 1 miliardo
MAX_REASONABLE_QTY = 1_000_000

def _build_optimize_line(...) -> OptimizeLine:
    unit = float(o.price or 0.0)

    # Validazione bounds
    if unit > MAX_REASONABLE_PRICE or unit < 0:
        log_warning("optimizer", "price", f"Invalid price {unit}, capping")
        unit = min(max(unit, 0), MAX_REASONABLE_PRICE)

    if q > MAX_REASONABLE_QTY or q < 0:
        log_warning("optimizer", "qty", f"Invalid qty {q}, capping")
        q = min(max(q, 0), MAX_REASONABLE_QTY)

    line_total = unit * q

    # Verifica overflow/inf
    if not math.isfinite(line_total):
        log_error("optimizer", "overflow", f"line_total overflow: {unit} * {q}")
        line_total = MAX_REASONABLE_PRICE  # Fallback sicuro

    return OptimizeLine(line_total=line_total, ...)
```

---

## Checklist Finale Round 2

Dopo aver applicato tutti i fix:

- [ ] FIX #15: N+1 query in KPI (HIGH)
- [ ] FIX #16: Quote file race condition (HIGH)
- [ ] FIX #20: Unbounded sitemap URLs (HIGH)
- [ ] FIX #21: Full table scan memory (HIGH)
- [ ] FIX #24: SSRF in fetch commands (HIGH)
- [ ] FIX #17: Gradio state mutation (MEDIUM)
- [ ] FIX #18: OverflowError in _safe_int (MEDIUM)
- [ ] FIX #19: Session/client leak (MEDIUM)
- [ ] FIX #22: Global cache race condition (MEDIUM)
- [ ] FIX #23: min() su sequenza vuota (MEDIUM)
- [ ] FIX #25: Integer overflow in line_total (MEDIUM)

**Quality Gates:**
```bash
uv run ruff check app/
uv run ruff format app/
uv run basedpyright app/
uv run pytest -v --tb=short
```

**Commit message suggerito:**
```
fix: resolve 11 functional bugs from skeptic review round 2

HIGH (DoS/Security):
- N+1 query + memory exhaustion in kpi_summary
- Quote file write race condition
- Unbounded sitemap URL count (DoS)
- Full table scan memory exhaustion
- SSRF vulnerability in fetch commands

MEDIUM:
- Gradio state mutation bug
- OverflowError not caught in _safe_int
- Session/client leak on auth failure
- Global cache race condition
- min() on empty sequence crash
- Integer overflow in line_total

Refs: assessment/skeptic-review-round2-2025-12-18.md
```

---

## Note Architetturali

Alcuni di questi bug indicano pattern problematici ricorrenti:

1. **Memory management**: Manca un pattern consistente per limitare risultati (paginazione)
2. **Thread safety**: Cache globali senza lock
3. **Input validation**: Manca layer di validazione centralizzato per URL e numeri
4. **Resource cleanup**: Pattern try/finally non applicato consistentemente

Considera un refactoring architetturale dopo aver fixato i bug urgenti.
