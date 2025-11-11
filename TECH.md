# Tecnologia (PN‑first)

Scelte principali
- Linguaggio/stack: Python 3.12, FastAPI, SQLAlchemy; httpx per HTTP; Selectolax/BeautifulSoup per HTML; pdfkit/wkhtmltopdf per PDF.
- Demo DB: SQLite con WAL; target Postgres.
- Tipi: Pydantic v2 ai bordi; niente Any/cast; un solo request/response per boundary.

Normalizzazione PN
- Regole: uppercase, trim, rimozione spazi/segni ("-", " ", "/"), soppressione suffissi noti (es. colori), dizionario alias (maker→varianti/dealer).
- Convalida: PNMapping.confidence; ancorare eventuale fuzzy a PN normalizzato con soglie conservative.

Crawling/Import
- Mapping YAML per sito/piattaforma: root/selectors per `name, price, brand, pn`, pagination `next`, detail follow, search `url_template`.
- Politiche: `delay`, `max_pages`, headers, auth (none/basic/form/token), rispetto robots/ToS.
- Parser deterministici con test su fixture HTML; probing carrello opzionale; LLM solo come fallback batch con guardrail (regex €, range importi, coerenza unità) e flag “da verificare”.

Estrazione policy dealer
- DealerPolicy derivato da pagine “Spedizioni/Condizioni/FAQ”: `base_cost`, `free_threshold`, `lead_days_std`, eventuale `cost_table`.
- Source/Confidence tracciati; override manuale via Impostazioni.

Ottimizzatore ordine
- Funzione obiettivo (v1): costo = somma(prezzi) + somma(spedizioni per dealer) + penale_dealer*(num_dealer-1) + penale_lead*(giorni_medi).
- Scenari pronti: “Miglior prezzo”, “Un solo dealer”, “Al massimo N dealer”, “Più veloce”.

Sicurezza e configurazione
- Credenziali dealer da `.env`/secret file; Basic Auth per endpoint sensibili in demo.
- Rate limit/retry: backoff con cap e jitter (250ms base, fattore 2, cap 8s, tentativi 3).

Strumenti e gate
- Esecuzione locale con `uv run`; lint/format con `uvx ruff`; typecheck con `uvx basedpyright`; test con `uv run pytest`.
- CONTROL.yaml definisce soglie coverage/complessità e KPI minimi.
