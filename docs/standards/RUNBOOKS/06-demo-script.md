---
title: Script Demo (60 secondi)
---

Obiettivo
Mostrare ricerca → affinamento facet → carrello → preventivo multi‑riga con PDF/HTML.

Passi (operatore)
1) Avvia servizi
   - Shell A: `make api`
   - Shell B: `make ui`
2) UI: apri http://localhost:7860
3) Ricerca: digita `sella` → clicca "Cerca"
4) Facet: espandi "Albero filtri" → scegli un valore (es. Velocità)
5) Carrello: seleziona un’offerta → imposta Qtà → "Aggiungi al carrello" (ripeti 2 articoli)
6) Preventivo: compila Cliente/Contatto → "Crea preventivo" → apri percorso HTML/PDF

Extra
- API check: `curl -s :8000/search -H 'content-type: application/json' -d '{"query_text":"sella"}' | jq`
- KPI: `curl -s :8000/kpi/today | jq`

Reset/Aggiornamento
- `make crawl-montanini` o `make crawl-ciclodiffusione Q="sella casco catena"`
- `uv run python -m app.cli reset-db` (distruttivo)
