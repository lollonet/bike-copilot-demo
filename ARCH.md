# Architettura (PN‑first)

Vista d’insieme
- Ingresso PN → Servizio di ricerca (locale) → Ranking (prezzo/disponibilità/lead) → Carrello → Preventivo PDF/HTML.
- Aggiornamento dati offline: motore di crawling/import che popola il DB locale da dealer multipli (web/CSV/PDF).

Dominio e Modello Dati (essenziale)
- Dealer(id, name, base_url, platform, active)
- DealerAccount(id, dealer_id, auth_kind, username, secret_ref, headers)
- ProductNormalized(id, maker_pn_norm, maker_pn_raw, brand, name, category)
- PNMapping(id, product_id, dealer_id, dealer_pn_norm, dealer_pn_raw, confidence)
- Offer(id, product_id, dealer_id, price, in_stock, lead_time_days, last_seen_ts, source)
- PriceHistory(id, offer_id, price, ts)
- AvailabilityHistory(id, offer_id, in_stock, lead_time_days, ts)
- DealerPolicy(id, dealer_id, base_cost, free_threshold, cost_table, lead_days_std, updated_at, source, confidence)
- CrawlJob(id, dealer_id, kind, status, started_at, finished_at, stats, error)
- RawIngest(id, dealer_id, url, payload, ts)

Boundary e Contratti (tipizzati)
- POST /search_pn → { maker_pn, qty?, dealers?, freshness_ttl? } → offerte per dealer con {price, in_stock, lead, last_seen_ts, source} e score.
- POST /quote → { items[{maker_pn, dealer_id?, qty}], customer, validity_days?, notes? } → HTML/PDF + URL.
- POST /facets_pn (opzionale) → sintetiche per filtro/diagnostica (solo se utili nel PN‑first).

Motore di Crawling (provider‑agnostico)
- Input: mapping YAML per piattaforma/sito (selettori, pagination, search template, politiche), credenziali opzionali.
- Pipeline: fetch (httpx) → parse (Selectolax/BS4) → normalizza PN/brand → upsert ProductNormalized/PNMapping/Offer → aggiorna storici → KPI.
- Policy extractor: parse pagine “Spedizioni/Condizioni/FAQ” con regole deterministiche; opzionale probing carrello e LLM con guardrail.

Osservabilità
- KPI: copertura PN, freschezza per dealer, tasso successo crawl, lag per dealer, PN non mappati.
- Log strutturati con trace_id e job_id.

Scalabilità e Deploy
- Demo: SQLite + WAL; no ingest concorrenti durante la demo.
- Target: Postgres, scheduler (APScheduler) o coda lavori; separazione lettura/scrittura.
