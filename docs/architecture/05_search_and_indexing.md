---
id: ARCH-V2-05
domain: docs
status: draft
---

# 05 — Search & Indexing

> Sistema di ricerca e indicizzazione prodotti aggregati.
> Volume: 50k–100k SKU, 50–200 query/giorno.

---

## Decisione: PostgreSQL FTS

### Scelta: PostgreSQL tsvector + pg_trgm

Il motore di ricerca full-text è integrato nel database (PostgreSQL 16) senza servizi aggiuntivi.

| Criterio | PostgreSQL FTS | MeiliSearch | Elasticsearch | SQLite FTS5 |
|----------|---------------|-------------|---------------|-------------|
| Servizio aggiuntivo | No (integrato) | Sì (container dedicato) | Sì (cluster JVM pesante) | No (ma SQLite scartato in s03) |
| Fuzzy / typo-tolerant | pg_trgm (buono) | Eccellente (nativo) | Buono (fuzziness param) | Limitato |
| Volumi 50k-100k | Nessun problema | Nessun problema | Overkill | Nessun problema |
| arm64 Docker | Integrato in postgres:16 | Immagine arm64 disponibile | Pesante, arm64 support | N/A |
| Risorse | Trascurabili (parte di PostgreSQL) | ~256 MB RAM | 2-4 GB RAM | N/A |
| Italiano stemming | Sì (dizionario `italian`) | Sì | Sì (plugin) | Limitato |

**MeiliSearch scartato**: eccellente per UX typo-tolerant, ma aggiunge un servizio da mantenere, sincronizzare, e monitorare. Per 200 query/giorno su un sistema single-user, PostgreSQL FTS è "good enough" e l'integrazione è zero-cost. MeiliSearch è un upgrade path per fase 2 se la qualità di ricerca non soddisfa.

**Elasticsearch scartato**: footprint JVM di 2-4 GB RAM, complessità operativa (cluster, sharding), overkill per il volume. Progettato per milioni di documenti e migliaia di query/secondo.

**Algolia scartato**: cloud-only, viola il vincolo self-hosted.

---

## Configurazione FTS

### Indici

```sql
-- Configurazione italiana per stemming e stop words
CREATE TEXT SEARCH CONFIGURATION italian_custom (COPY = italian);

-- Indice GIN per full-text search su canonical_product
CREATE INDEX idx_canonical_product_fts
ON canonical_product
USING GIN (to_tsvector('italian_custom', coalesce(name, '') || ' ' || coalesce(brand, '')));

-- Indice GIN per trigram similarity (fuzzy)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_canonical_product_trgm
ON canonical_product
USING GIN ((name || ' ' || coalesce(brand, '')) gin_trgm_ops);

-- Indice su supplier_listing per ricerca per fornitore
CREATE INDEX idx_supplier_listing_fts
ON supplier_listing
USING GIN (to_tsvector('italian_custom', name));
```

### Query di Ricerca

```sql
-- Ricerca combinata: FTS ranking + trigram similarity
WITH search_results AS (
    SELECT
        cp.id,
        cp.name,
        cp.brand,
        cp.ean,
        ts_rank(
            to_tsvector('italian_custom', cp.name || ' ' || coalesce(cp.brand, '')),
            plainto_tsquery('italian_custom', :query)
        ) AS fts_rank,
        similarity(
            cp.name || ' ' || coalesce(cp.brand, ''),
            :query
        ) AS trgm_sim
    FROM canonical_product cp
    WHERE
        to_tsvector('italian_custom', cp.name || ' ' || coalesce(cp.brand, ''))
        @@ plainto_tsquery('italian_custom', :query)
        OR similarity(cp.name || ' ' || coalesce(cp.brand, ''), :query) > 0.3
)
SELECT
    sr.*,
    sl.supplier_id,
    sl.price,
    sl.availability,
    sl.delivery_days,
    s.name AS supplier_name
FROM search_results sr
JOIN supplier_listing sl ON sl.canonical_product_id = sr.id
JOIN supplier s ON s.id = sl.supplier_id
WHERE sl.availability != 'out_of_stock'
ORDER BY
    -- EAN exact match sempre primo
    CASE WHEN sr.ean = :query THEN 0 ELSE 1 END,
    -- Score combinato
    (0.6 * sr.fts_rank + 0.4 * sr.trgm_sim) DESC
LIMIT 50;
```

---

## Ranking Strategy

| Componente | Peso | Descrizione |
|-----------|------|-------------|
| **Text relevance** | 60% | `ts_rank` (FTS) + `similarity` (trigram) |
| **Disponibilità** | 20% | in_stock = 1.0, low_stock = 0.6, out_of_stock = 0.1, unknown = 0.3 |
| **Prezzo** | 20% | Normalizzato: `1 - (price - min_price) / (max_price - min_price)` |
| **EAN exact match** | Override | Se la query è un EAN valido e corrisponde, il prodotto va in cima |

---

## Cache Layer

### Decisione: Redis con TTL 15 minuti

| Criterio | Redis cache | In-memory LRU | No cache |
|----------|-------------|---------------|----------|
| Persistenza restart | Sì (Redis persistent) | No | N/A |
| Condivisione worker | Sì | No (per-process) | N/A |
| Complessità | Bassa (Redis già presente per RQ) | Minima | Zero |
| Beneficio UX | Buono (ricerche ripetute istantanee) | Buono | N/A |

Redis è già nel docker-compose per RQ → nessun container aggiuntivo.

**Cache key**: `search:{sha256(normalized_query + supplier_filter_hash)}`
**Invalidazione**: alla fine di ogni scraping job per il fornitore interessato (`supplier_id`).
**TTL**: 15 minuti (sufficiente per sessione di ricerca, non troppo lungo per dati stale).

---

## Data Freshness / Error Budgets

| Indicatore | Soglia | Azione UI |
|-----------|--------|-----------|
| 🟢 Fresh | `last_scraped_at` < 24h | Nessun avviso |
| 🟡 Aging | 24h ≤ `last_scraped_at` < 48h | Badge "Dati di ieri" |
| 🔴 Stale | `last_scraped_at` ≥ 48h | Banner "Dati non aggiornati — ultimo scraping: [data]" |
| ⚫ Mai scrapato | `last_scraped_at` NULL | "Fornitore non ancora sincronizzato" |

- I risultati vengono **sempre mostrati** anche con dati stale, con avviso visivo.
- L'utente può triggerare un refresh on-demand per un fornitore specifico.
- L'optimizer (s07) usa `last_scraped_at` per pesare l'affidabilità dei dati.

---

## Considerazioni Dominio Ciclismo

### Sinonimi e Abbreviazioni

| Abbreviazione | Espansione |
|--------------|------------|
| cambio post. | cambio posteriore |
| fr. / ant. | freno / anteriore |
| der. | deragliatore |
| RD | rear derailleur |
| FD | front derailleur |
| BB | bottom bracket / movimento centrale |

**Fase 1**: normalizzazione base (lowcase, trim, remove punctuation). Nessun dizionario sinonimi.

**Fase 2**: dizionario sinonimi ciclismo come configurazione PostgreSQL custom `ALTER TEXT SEARCH DICTIONARY`.

### Normalizzazione Brand

```sql
-- Brand normalizzato a lowercase per confronto
CREATE INDEX idx_canonical_product_brand_lower
ON canonical_product (lower(brand));
```

Shimano = SHIMANO = shimano → match normalizzato.

---

## Rischi Residui

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Qualità fuzzy su termini italiani ciclismo | Risultati irrilevanti | Soglia trigram conservativa (0.3), feedback utente |
| Performance FTS a 100k documenti | Query lente | Benchmark in Phase 1.5, GIN index, LIMIT |
| Sinonimi non coperti | Ricerche con abbreviazioni falliscono | Dizionario sinonimi fase 2 |
| Cache stale durante aggiornamento | Risultati vecchi per 15 min | TTL breve, invalidazione su scraping |

---

## Open Questions

1. **Benchmark FTS vs MeiliSearch**: quanto è migliore MeiliSearch per query tipiche ciclismo? → Phase 1.5 spike con 10k prodotti sample
2. **Dizionario sinonimi**: quanto è grande il vocabolario di abbreviazioni ciclismo italiano? → Raccogliere durante uso reale fase 1
3. **Stemming italiano**: lo stemmer PostgreSQL gestisce bene i termini tecnici ciclismo? → Verificare con query reali

---

## Dipendenze

| Direzione | Sezione | Relazione |
|-----------|---------|-----------|
| **← s03** | Tech Stack | PostgreSQL 16 con pg_trgm |
| **← s04** | Data Model | Schema `canonical_product`, `supplier_listing`, indici |
| **→ s08** | UI Architecture | API di ricerca consumata dalla UI |
| **→ s07** | Order Optimizer | Risultati ricerca come input per selezione prodotti |
