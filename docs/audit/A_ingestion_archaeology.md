---
id: AUDIT-A
domain: docs
status: draft
---

# Audit A — Ingestion Archaeology

Audit statico della pipeline di ingestion. Solo lettura codice, nessuna esecuzione.

## Fatti

### Q1. Stack di Scraping per Fornitore

| Fornitore | Login | Navigation | Parsing | Persistenza |
|-----------|-------|------------|---------|-------------|
| **RMS** | httpx SPA JSON auth (`service_helpers.py:379-409`), env `DEALER_RMS_*` | httpx GET con session cookies | BeautifulSoup (`web_adapter.py:186`) con CSS selectors da `web-rms.yaml` | `ProductInput`/`OfferInput` → `ingest.py:37` `upsert()` |
| **Ciclodiffusione** | httpx form POST (`service_helpers.py:276-303`), env `DEALER_CICLODIFFUSIONE_*` | httpx GET + detail page follow (`web_adapter.py:735-761`) | BeautifulSoup con CSS + OG meta tags da `web-ciclodiffusione.yaml` | Idem |
| **CicloPromo** | httpx form POST multipart (`service_helpers.py:276-303`), env `DEALER_CICLOPROMO_*` | httpx GET + query pagination skip-based | BeautifulSoup con CSS da `web-ciclopromo.yaml` | Idem |
| **Montanini** | Nessuno (sito pubblico) | httpx GET via sitemap XML (`ingest_helpers.py:126-154`) + detail page follow | BeautifulSoup con CSS da `web-ciclimontanini.yaml` | Idem |

**Playwright**: opzionale, lazy-loaded (`playwright_fetcher.py:33-38`). Usato solo nei test di integrazione (`test_b2b_integration.py`). Il runtime path di ingestion usa **httpx** per tutti i fornitori.

### Q2. Localizzazione della Logica

**Confine netto**: selettori CSS in YAML (`providers/web-*.yaml`), post-processing in Python (`web_adapter.py`).

| Logica | Dove | Esempio |
|--------|------|---------|
| Selettori CSS (root, name, price, brand, mpn) | YAML mapping | `web-ciclopromo.yaml:3-8` |
| Detail page selectors | YAML `detail:` block | `web-ciclodiffusione.yaml:17-24` |
| Pagination config | YAML `pagination:` block | `web-ciclopromo.yaml:10-13` |
| Price parsing (€, virgola, punto) | Python `_to_price()` | `web_adapter.py:120-142` |
| Stock boolean coercion | Python `_to_bool()` | `web_adapter.py:105-117` |
| Product validation (brand+mpn required) | Python `_parse_listing_row()` | `web_adapter.py:199-206` |

### Q3. Surface Area di Estrazione

| Campo | RMS | Ciclodiffusione | CicloPromo | Montanini |
|-------|-----|-----------------|------------|-----------|
| brand | estratto (`web-rms.yaml:6`) | estratto (detail `itemprop='brand'`) | estratto (`web-ciclopromo.yaml:7`) | estratto (da titolo, placeholder) |
| mpn | estratto (`web-rms.yaml:7`) | estratto (detail `itemprop='sku'`) | estratto (`web-ciclopromo.yaml:8`) | estratto (detail `.product_meta .sku`) |
| name | estratto | estratto | estratto | estratto |
| price | estratto | estratto | estratto | estratto |
| category | estratto | estratto (breadcrumb) | estratto | estratto (detail `.posted_in a`) |
| in_stock | **BUG: key `stock` ≠ `in_stock`** | estratto (OG availability) | mai-estratto | estratto (detail `.stock`) |
| lead_time | **BUG: key `lead_time` ≠ `lead_time_days`** | mai-estratto (vuoto) | mai-estratto | mai-estratto |
| dealer_code | mai-estratto | estratto (`itemprop='sku'`) | mai-estratto | mai-estratto |
| EAN | mai-estratto | mai-estratto | mai-estratto | mai-estratto |
| immagini | mai-estratto | mai-estratto | mai-estratto | mai-estratto |
| descrizione | mai-estratto | mai-estratto | mai-estratto | mai-estratto |
| sconti scaglione | mai-estratto | mai-estratto | mai-estratto | mai-estratto |

### Q4. Failure Modes (3 classi)

**Classe A — Dropped Rows (silenzioso)**: Se `brand`, `mpn`, o `price` sono assenti dopo CSS select, il prodotto viene scartato con `return None, None` (`web_adapter.py:199-206`). Nessun log, nessuna eccezione. Con un selettore CSS rotto su `root`, 0 righe trovate → 0 prodotti, nessun errore.

**Classe B — Coerced Wrong Values (silenzioso)**: `_to_price()` (`web_adapter.py:120-142`) converte stringhe non parsabili a `0.0`. `_to_bool()` (`:105-117`) converte stringhe non riconosciute a `False`. Un selettore che punta all'elemento sbagliato produce dati errati che entrano nel DB senza alert.

**Classe C — YAML/Parser Key Drift (BUG CONFERMATO)**: `web-rms.yaml:15-16` usa chiavi `stock` e `lead_time`. Il `WebMapping` TypedDict (`web_adapter.py:33-52`) riconosce solo `in_stock` e `lead_time_days`. **Risultato: stock e lead_time di RMS vengono silenziosamente ignorati.** Il parser li tratta come chiavi sconosciute → il campo non viene estratto → `in_stock` defaulta a `False`, `lead_time_days` a `None`.

### Q5. Test e Fixture

**Fixture HTML salvate** (`providers/html/`):

| Fornitore | File fixture | Usati nei test? |
|-----------|-------------|-----------------|
| CicloPromo | `ciclopromo-fixture.html`, `e-Shop _ CICLOPROMO.html`, `Occhiali Magicshine...html` | Si (`test_web_adapter.py:347-368`) |
| Ciclodiffusione | `CAMBIO MTB SHIMANO...html`, `DISCHI FRENO...html`, `storeden-product.html` | Si (`test_web_adapter.py:40-49` via storeden) |
| RMS | `B2B_rms.html`, `RMS Ciclo...html` | **No** — nessun test offline RMS |
| Montanini | `woo-sale.html` (generico WooCommerce) | Si (`test_web_adapter.py` via woo-sale) |
| Generico | `example.html` | Si (`test_web_adapter.py:20-38`) |

**Test per fornitore**:

| Tipo | File | Test# | Network? |
|------|------|-------|----------|
| Parser offline generici | `test_web_adapter.py` | 11 | No |
| CicloPromo fixture | `test_web_adapter.py:347-368` | 1 | No |
| Ciclodiffusione (storeden) | `test_web_adapter.py:40-49` | 1 | No |
| RMS offline | — | **0** | — |
| Montanini offline | — (woo-sale e' generico) | 0 specifici | — |
| Integration (tutti) | `test_b2b_integration.py` | 6 (3 auth + 3 accessibility) | **Si** (skipped senza creds) |
| Ingest pipeline | `test_ingest.py` | 4 | No |
| CSV/mapped CSV | `test_csv_adapter.py`, `test_csv_mapped_adapter.py` | 6 | No |

### Q6. Schema di Output

**Uniforme**. Tutti i parser convergono su 2 Pydantic models (`app/types.py:210-232`):
- `ProductInput`: brand, mpn, ean, name, category, speed, brake, axle, rotor, freehub
- `OfferInput`: brand, mpn, supplier, price, in_stock, lead_time_days, currency, extra (dict)

Scrittura DB via `ingest.py:37-62` `upsert()` → SQLAlchemy models `Product` (`models.py:52-70`) e `SupplierOffer` (`models.py:75-97`). Il campo `extra` (JSON) conserva dati fornitore-specifici come `dealer_pn`.

**Supplier non e' un'entita' separata**: stringa su `SupplierOffer.supplier` (`models.py:80`).

### Rate-Limiting e Scraping Etiquette

| Aspetto | Implementazione | Evidenza |
|---------|----------------|----------|
| Delay tra richieste | `delay_sec` parametro, default 0.75s per montanini (`ingest_helpers.py:151`) | `web_adapter.py:791-792` |
| User-Agent | Statico `"BikeCopilotBot/0.1"` su tutti i client | `web_adapter.py:511`, `service_helpers.py:78` |
| User-Agent rotation | **Assente** | — |
| Cookie persistence | Per-session httpx.Client, non cross-session | `service_helpers.py:79-82` |
| Proxy | **Assente** | — |
| robots.txt | **Non rispettato** (nessun check) | — |

---

## Interpretazione

**Pattern sano**: architettura YAML-driven con schema di output uniforme. Il confine selettori/parsing e' pulito. L'astrazione `ProductInput`/`OfferInput` garantisce uniformita' cross-fornitore.

**Pattern patologico**: **failure totalmente silenzioso**. Un selettore rotto produce 0 prodotti OPPURE dati sbagliati senza nessun segnale. Nessun alert, nessun contatore "prodotti estratti vs attesi", nessun checksum. Il sistema non distingue "0 prodotti perche' il catalogo e' vuoto" da "0 prodotti perche' il selettore e' rotto".

**Key drift confermato**: `web-rms.yaml` usa chiavi incompatibili (`stock` vs `in_stock`, `lead_time` vs `lead_time_days`). **Tutti i prodotti RMS nel DB hanno `in_stock=False` e `lead_time_days=None` anche se il sito mostra disponibilita'.** Questo e' un data corruption silenzioso attivo.

**Asimmetria fornitori**: Ciclodiffusione ha il parser piu' sofisticato (detail pages con OG meta, sku, breadcrumb). CicloPromo ha buona coverage con pagination. RMS ha il mapping piu' fragile (key drift + zero test offline). Montanini funziona via sitemap senza auth.

---

## Verdetto

| Fornitore | Rating | Motivazione |
|-----------|--------|-------------|
| **CicloPromo** | **yellow** | Parser funzionale con pagination. Fixture offline presente. Ma: nessun test di stock/lead_time (non estratti), login non testato offline |
| **Ciclodiffusione** | **yellow** | Parser piu' completo (detail pages, OG meta, sku). Ma: un solo test offline (storeden generico), login form non testato offline |
| **RMS** | **red** | **Key drift confermato**: `stock`/`lead_time` ignorati → dati corrotti silenziosamente. Zero test offline. Login SPA non testato offline |
| **Montanini** | **yellow** | Funziona senza auth (sitemap pubblico). WooCommerce standard. Ma: brand/mpn sono placeholder nel mapping (estratti da titolo prodotto) |

**Rubric usata**: auth completeness (login testabile?), parser/mapping compatibility (chiavi YAML matchano WebMapping?), offline fixture coverage (test senza rete?), silent-failure exposure (dati errati senza alert?).

---

## Open Questions

1. **Le credenziali .env sono ancora valide?** Non determinabile da codice — richiede login reale
2. **I portali hanno cambiato DOM durante la pausa?** Non determinabile — richiede fetch reale e confronto con fixture
3. **Il key drift RMS e' l'unico o ci sono altri?** Parzialmente determinabile: ho verificato solo `stock`/`lead_time`. Servirebbero test exhaustivi su tutte le chiavi YAML vs WebMapping
4. **I selettori CicloPromo/Ciclodiffusione sono ancora validi?** Le fixture in `providers/html/` sono datate — servono capture fresche
5. **Quanto sono robusti i parser di prezzo con formati diversi?** `_to_price()` gestisce €, virgole, punti — ma non testato con formati esotici dei fornitori reali

---

## Action Items

1. **FIX IMMEDIATO**: Correggere `providers/web-rms.yaml:15-16` — rinominare `stock` → `in_stock` e `lead_time` → `lead_time_days`. **1 minuto, 2 righe, impatto critico** (risolve data corruption silenzioso)

2. **PRE-CREDENZIALI**: Aggiungere test offline per RMS usando fixture `providers/html/B2B_rms.html` gia' presente ma non usata. Validare che i selettori CSS matchano l'HTML salvato. **2-3h**

3. **PRE-CREDENZIALI**: Aggiungere contatore "prodotti estratti" post-parsing con warning se count=0 (distinguere "catalogo vuoto" da "selettore rotto"). In `web_adapter.py` dopo `_parse_listing_row` loop. **1-2h**

4. **GIORNO-CREDENZIALI**: Catturare HTML fresco per tutti i fornitori e salvare come fixture aggiornate in `providers/html/`. Confrontare con fixture esistenti per rilevare drift DOM. **2-4h**

5. **POST-MVP**: Aggiungere validazione chiavi YAML vs `WebMapping` TypedDict al load time — rifiutare chiavi non riconosciute con errore esplicito invece di ignorarle. **2-3h**
