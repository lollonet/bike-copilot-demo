# Runbook 09 — Crawling operativo (sicuro e ripetibile)

Obiettivo
- Eseguire il crawling in modo sicuro (ToS/robots), ripetibile e misurabile.

Passi
- Configura delay/jitter, `max_pages`, user‑agent e (se necessario) header Cookie.
- Evita ingest concorrenti sullo stesso dealer; usa job separati.
- Salva RawIngest per audit; aggiorna Offer/History in upsert idempotenti.
- Monitora KPI: freschezza, errori per dealer, lag.

Esiti
- Cataloghi aggiornati con consistenza e senza sovraccaricare i siti.
