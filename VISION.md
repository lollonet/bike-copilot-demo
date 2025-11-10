# vision

Why: help a bike shop quote parts fast and confidently from mixed supplier sources (CSV, PDF, websites) entirely offline on a single Linux Mint box, with a clean path to real APIs later.

Who
- Owner/Mechanic: searches parts, chooses top option, generates a quote.
- Operator: keeps lists up to date (drops CSV/PDF), checks KPIs.
- Integrator: later adds supplier APIs/ERP without breaking the flow.

Outcomes (what “good” looks like)
- One‑click quote: search → select → PDF/HTML ready in under 30 seconds.
- Top‑3 proposals with clear pros/cons (price, stock, lead time, compatibility).
- Local, robust demo: no Internet required for core flows; service managed by systemd.
- Extensible ingest: add a provider by writing an adapter only; no core rewrites.

Success Metrics
- TtQ (time‑to‑quote): P50 ≤ 30s; P95 ≤ 60s.
- Ingest friction: drop CSV/PDF and run one command; P95 runtime ≤ 2 min for 10k rows.
- Search precision: ≥ 95% of demo scenarios return a plausible top‑3.
- Operability: startup ≤ 3s; zero type errors; ruff=0 findings; tests ≥ 85% coverage once added.

Non‑Goals
- Full ERP, inventory write‑back, payments, or multi‑tenant SaaS.
- Advanced auth beyond Basic Auth for demo endpoints.
- “Perfect” PDF parsing for all catalogs (we target common, table‑like PDFs).

Risks & Mitigations
- PDF variance: isolate in adapters; keep raw → staged → normalized pipeline with hashes.
- Data quality: prefer EAN/GTIN; log collisions; keep fuzzy matching configurable.
- Concurrency on SQLite: enable WAL; serialize ingest vs. live demo.
- Legal/ToS: prefer official files/APIs; scrape only with permission and etiquette.

Milestones
- M1 Demo‑Lite (CSV) — search, top‑3, quote HTML/PDF, KPI basics.
- M2 PDF Ingest — add PdfTable adapter + staging with provenance.
- M3 Web Adapter — provider fetcher with cache and rate limits.
- M4 Hardening — auth for /quote,/kpi; systemd deployment path; tests to 85%.

