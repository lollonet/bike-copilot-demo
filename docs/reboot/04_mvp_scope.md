---
id: REBOOT-04
domain: docs
status: draft
---

# 04 — MVP Scope Freeze

## IN-SCOPE (8 item)

| # | Item | Pre-condizione | Effort base | Note |
|---|------|---------------|-------------|------|
| 1 | **Env validation**: `uv sync`, `playwright install chromium`, verificare Python | Nessuna | 2h | T0 nella roadmap |
| 2 | **Commit/stash uncommitted changes** su fix/log-002 | Nessuna | 0.5h | Prima di qualsiasi merge |
| 3 | **Merge PR #85-#88** (security/logging) con re-test | Cascade review (fatta in 00_state) | 4h | Condizionale: solo dopo re-test post-merge |
| 4 | **Verificare credenziali + login** su 3 fornitori reali | PR mergiate, env ripristinato | 6h | GATE: se fallisce, STOP e debug |
| 5 | **Scraping smoke test**: 1 pagina per fornitore, verificare parsing | Login funzionante | 4h | GATE: se parser rotti, fix selettori |
| 6 | **Search + optimizer test** con dati reali da ingest | Scraping OK | 4h | Fix BIZ-001 (min default) incluso |
| 7 | **Preventivo HTML** da carrello reale | Search + optimizer OK | 2h | PDF solo se wkhtmltopdf installabile facilmente |
| 8 | **Demo walkthrough** end-to-end completo | Tutto sopra | 3h | Prova del budino finale |

**Pre-condizione globale**: `make reset-db` prima di ingest dati reali (wipare dati demo).

**Totale base**: ~26h + 8h contingency post-gate = **34h**

---

## OUT-SCOPE (con motivazione)

| Item | Provenienza | Motivazione esclusione |
|------|-------------|----------------------|
| #89 SEC-007: Input validation + rate limiting | 6-council audit | Single-user locale, nessun rischio di abuse |
| #90 DATA-001: Transaction boundaries | 6-council audit | Volume dati demo piccolo, rischio trascurabile |
| #91 PERF-001: Full table scan elimination | 6-council audit | <10k prodotti demo, performance accettabile |
| #92 ARC-003: web_adapter split | 6-council audit | Funziona per demo, refactoring e' polish |
| #94 TEST-001: Test coverage gaps | 6-council audit | Test manuali durante demo sono sufficienti |
| #95 OPS-001: Alembic + health checks | 6-council audit | SQLite + create_all() sufficiente per demo locale |
| ADR-002 rewrite (HTMX) | ADR drift | Gradio funziona per demo, rewrite costerebbe settimane |
| PostgreSQL migration | docs/architecture | SQLite deciso da ADR-001, sufficiente per validazione |
| Docker Compose deploy | docs/architecture | Run diretto su Mac Studio sufficiente per demo |
| Redis + RQ job queue | docs/architecture | Scraping sincrono sufficiente per 3 fornitori |
| PuLP ILP optimizer | docs/architecture | Greedy funziona per demo con 3 fornitori |
| Nuovi fornitori | docs/architecture/11 | Solo 3 fornitori per MVP |
| Pulizia branch stale | Housekeeping | Cosmetico, nessun impatto su demo |

---

## Budget Riepilogo

| Scenario | Ore | Settimane (part-time ~15h/sett) |
|----------|-----|-------------------------------|
| Best case | 18h | 1.2 settimane |
| **Base case** | **34h** | **2.3 settimane** |
| Worst case | 62h | 4.1 settimane |

Il base case sta nel budget di 2-3 settimane. Il worst case sfora — accettabile perche' include remediation per credenziali scadute + DOM rotti + parser fix.
