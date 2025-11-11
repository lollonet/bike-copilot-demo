---
title: Demo Script (60 seconds)
---

Goal
Show search → facet tweak → cart → multi‑item quote with PDF/HTML.

Steps (operator)
1) Start services
   - Shell A: `make api`
   - Shell B: `make ui`
2) UI: open http://localhost:7860
3) Search: type `sella` → Click "Cerca"
4) Facets: expand "Albero filtri" → pick one value (e.g., Velocità)
5) Add to cart: select an offer → set Qtà → "Aggiungi al carrello" (repeat 2 items)
6) Quote: fill Cliente/Contatto → "Crea preventivo" → open HTML/PDF path

Extras
- API check: `curl -s :8000/search -H 'content-type: application/json' -d '{"query_text":"sella"}' | jq`
- KPI: `curl -s :8000/kpi/today | jq`

Reset/Refresh
- `make crawl-montanini` or `make crawl-ciclodiffusione Q="sella casco catena"`
- `uv run python -m app.cli reset-db` (destructive)

