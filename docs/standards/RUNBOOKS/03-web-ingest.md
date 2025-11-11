---
title: Web Ingest Runbook (Woo/Storeden)
---

Purpose
- Safely crawl product data for demo purposes using mapping YAMLs. Prefer vendor APIs when available.

Safety
- Be polite: add delay ≥ 0.75s; follow redirects; normalize relative links.
- Use small page caps for tests; scale gradually.
- If rate-limited, pass a browser Cookie via `--header "Cookie: ..."`.

WooCommerce (Cicli Montanini)
- Mapping: `providers/web-ciclimontanini.yaml`
- Full ingest via sitemap (recommended):
  - `uv run python -m app.cli fetch-sitemap --sitemap https://www.ciclimontanini.com/product-sitemap.xml --mapping providers/web-ciclimontanini.yaml --contains /prodotto/ --delay 0.75`
  - `uv run python -m app.cli fetch-sitemap --sitemap https://www.ciclimontanini.com/product-sitemap2.xml --mapping providers/web-ciclimontanini.yaml --contains /prodotto/ --delay 0.75`
- Category extraction: detail page `.posted_in` (adapter handles it).

Storeden (Ciclodiffusione)
- Mapping: `providers/web-ciclodiffusione.yaml`
- Search ingest (per keyword):
  - `uv run python -m app.cli search-web --query "sella" --mapping providers/web-ciclodiffusione.yaml --max-pages 3 --delay 0.8`
- Category extraction: breadcrumb links (adapter handles it).

Make Targets (if defined)
- `make crawl-montanini`
- `make crawl-ciclodiffusione Q="sella casco catena"`

Notes
- Verify facets via: `curl -s :8000/facets -H 'content-type: application/json' -d '{"query_text":"sella"}' | jq`
- Re‑ingest to refresh categories when adapters improve.

