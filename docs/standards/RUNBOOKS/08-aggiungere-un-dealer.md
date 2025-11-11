# Runbook 08 — Aggiungere un dealer

Obiettivo
- Registrare un nuovo dealer senza modifiche al codice, usando un mapping YAML e (se serve) credenziali.

Passi
- Crea mapping in `providers/` con: piattaforma, selettori (lista/detail), pagination `next`, `search.url_template`, politiche (delay/max_pages), auth.
- (Opz.) Imposta credenziali in `.env` o secret file.
- Dry‑run ingest: una categoria o una ricerca esempio; controlla log ed esiti (PN/brand/price/stock).
- Pianifica crawling con delay “gentile”; misura freschezza e fallimenti.

Esiti
- Dealer comparirà in UI e sarà usabile dall’ottimizzatore.
