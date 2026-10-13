---
id: REBOOT-00
domain: docs
status: draft
---

# 00 — State Reconstruction (FORENSIC)

## Executive Summary

**Top blockers**: 4 PR security/logging pronte ma non mergiate da mesi; uncommitted changes su branch attivo; credenziali B2B probabilmente scadute.

**Decisioni pending**: merge/abandon delle 4 PR; ratifica Gradio vs HTMX (ADR-002); triage 8 issue aperte.

**Next 3 actions**: (1) stash/commit changes su branch corrente; (2) cascade review + merge PR #85-#88; (3) verificare credenziali .env.

---

## Sezione A — FATTI

### Timeline Recente (commit su main)

| Data approx | SHA | Descrizione |
|-------------|-----|-------------|
| Gen 2026 | `a3883c9` | Remove CHANGELOG.md.backup (#84) |
| Gen 2026 | `6e8acb6` | ARC-002 Phase 4: Extract service commands (#83) |
| Gen 2026 | `0901e2e` | ARC-002 Phase 3: Extract data commands (#82) |
| Gen 2026 | `0c302d5` | ARC-002 Phase 2: Extract ingest commands (#81) |
| Gen 2026 | `b1dd550` | ARC-002 Phase 1: Extract fetch commands (#80) |
| Gen 2026 | `661fc7d` | ARC-001 Phase 3c: Extract cart & quote handlers (#79) |
| Gen 2026 | `199c721` | ARC-001 Phase 3b: Consolidate facet handlers (#78) |
| Gen 2026 | `70c1f21` | ARC-001 Phase 3a Steps 2-3: Extract search handler (#77) |
| Gen 2026 | `eef0d5d` | ARC-001 Phase 3a Step 1: Extract UI helpers (#75) |
| Gen 2026 | `731790e` | ARC-001 Phase 1-2: Initial architectural refactoring (#74) |
| Gen 2026 | `8f1f7a6` | Complete rewrite of REQ, ARC, TECH documentation (#71) |
| Dic 2025 | `216a81c`→`ea5b6d1` | CI improvements, Claude workflows, security scanning |
| Dic 2025 | `7c3a222` | REQ-007: restore trace context and record price changes |
| Dic 2025 | `4abbb27` | REQ-001: apply skeptic review bugfixes |
| Dic 2025 | `bfcfe31` | REQ-001: crawl all dealers using seed URLs |
| Dic 2025 | `fb8918d` | REQ-001: fix type checks for web adapter |

**Attivita' completata**: refactoring architetturale (ARC-001 UI -35.6%, ARC-002 CLI -59.7%), CI/CD setup completo, security scanning, documentation rewrite.

### Branch Matrix

| Branch | Intent | Stale? | Superseded? |
|--------|--------|--------|-------------|
| `main` | Trunk stabile | No | — |
| `fix/sec-003-https-verification` | SSL verify=True su tutti httpx.Client | No | No — PR #85 |
| `fix/sec-004-unbounded-timeouts` | max_total_seconds DoS prevention | No | No — PR #86 |
| `fix/log-001-silent-exceptions` | Logging su exception handler critici | No | No — PR #87 |
| `fix/log-002-trace-id-propagation` | **CORRENTE** — trace_id ContextVar fix | No | No — PR #88 |
| `feature/arc-001-phase-3a-step-2-3` | Residuo refactoring UI | Si | Si — gia mergiato via #77 |
| `claude-refactor` | Vecchio branch refactoring | Si | Si |
| `feat/docs-refactor-gemini` | Docs refactoring Gemini | Si | Si |
| `gemini-integration` | Integrazione Gemini | Si | Probabile |
| `fix/docs-cleanup` | Cleanup docs | Si | Probabile |

### Uncommitted Changes (branch corrente `fix/log-002-trace-id-propagation`)

| File | Modifica | Origine |
|------|----------|---------|
| `app/adapters/web_adapter.py` | Timeout threading attraverso detail-link chain (6 funzioni modificate) | fix-review PR #88 |
| `tests/test_fetch_timeout.py` | Class variable → closure variable per test isolation | fix-review PR #88 |

### Stash

| # | Branch originale | Contenuto |
|---|-----------------|-----------|
| `stash@{0}` | skeptic-review-bugfix-2025-12-18 | WIP skeptic review bugfixes |
| `stash@{1}` | main | pre-merge |

### Mappa PR Aperte

| PR | Titolo | Branch | Linee | Reviewer | Stato review |
|----|--------|--------|-------|----------|-------------|
| #85 | SEC-003: SSL verification | fix/sec-003 | +279/-75 | codex-connector | Reviewed |
| #86 | SEC-004: DoS timeout | fix/sec-004 | +514/-98 | codex-connector | Reviewed |
| #87 | LOG-001: Silent exceptions (partial) | fix/log-001 | +546/-102 | codex-connector | Reviewed |
| #88 | LOG-002: trace_id propagation | fix/log-002 | +546/-110 | codex-connector | Reviewed |

### Mappa Issue Aperte

| # | Titolo | Label | Origine |
|---|--------|-------|---------|
| #46 | LOG-001: 72% silent exception handlers | security | Audit iniziale (Nov 2025) |
| #89 | SEC-007: API input validation & access control | security, priority:high | 6-council audit (Mar 2026) |
| #90 | DATA-001: Ingest transaction boundaries | bug, data-integrity | 6-council audit |
| #91 | PERF-001: Full table scans in search/PN | performance, priority:high | 6-council audit |
| #92 | ARC-003: web_adapter complexity & DRY | refactoring, architecture | 6-council audit |
| #93 | BIZ-001: Search ValueError on all-None prices | bug | 6-council audit |
| #94 | TEST-001: 4 untested modules, missing E2E | testing | 6-council audit |
| #95 | OPS-001: DB migrations, health checks, deps | ops, priority:medium | 6-council audit |

---

## Sezione B — VERDETTI

### Rubric Decisionale PR

| Criterio | merge-as-is | rebase+merge | close+redo | abandon |
|----------|-------------|-------------|------------|---------|
| Conflitti | 0 | Pochi, risolvibili | Molti, estesi | — |
| Behavioral risk | Nessuno/basso | Basso | Alto | — |
| Test impact | Test passano | Test adattabili | Test rotti | — |
| Manual retest | Non necessario | Minimo | Esteso | Branch morto |

### Cascade Analysis PR

**PR #85 (SEC-003 SSL)**: Aggiunge `verify=True` a 8 httpx.Client. Impatto comportamentale: nessuno (verify=True e' gia il default). Test: 5 mock aggiornati per accettare param verify. Cascata: nessuna.

**PR #86 (SEC-004 Timeout)**: Aggiunge `max_total_seconds` a `fetch_and_parse_urls()`. Impatto: nuovo parametro con default 600s, backward compatible. Cascata: nessuna su search/optimizer/quote — solo scraping.

**PR #87 (LOG-001 Logging)**: Aggiunge `log_event()`/`log_exception()` a 4 handler. Impatto: solo logging aggiuntivo, nessun cambio di flusso. Cascata: nessuna.

**PR #88 (LOG-002 trace_id)**: Rimuove `trace_id=None` da 8 chiamate. Impatto: trace_id ora propagato automaticamente via ContextVar. Cascata: bassa — miglioramento observability, nessun cambio funzionale.

**NOTA**: Il branch corrente (fix/log-002) ha anche uncommitted changes dal fix-review che threading timeout params e fixano test isolation. Questi vanno committati PRIMA del merge.

### PR Verdict

| PR | Verdict | Motivazione |
|----|---------|-------------|
| #85 | **merge-as-is** | Zero conflitti, zero rischio comportamentale, test aggiornati |
| #86 | **merge-as-is** | Backward compatible, nuovo param con default sicuro |
| #87 | **merge-as-is** | Solo logging aggiuntivo, nessun side effect |
| #88 | **rebase+merge** | Serve prima: commit uncommitted changes, poi rebase su main post-merge #85-87 |

### Issue Verdict

| # | Verdict | Motivazione |
|---|---------|-------------|
| #46 | **post-MVP** | Parzialmente fixato da PR #87. Handler rimanenti sono parsing helpers con fallback atteso |
| #89 | **post-MVP** | Input validation e rate limiting non servono per demo single-user locale |
| #90 | **post-MVP** | Transaction boundaries: rischio basso con volume dati demo |
| #91 | **post-MVP** | Full table scan: performance accettabile con <10k prodotti demo |
| #92 | **post-MVP** | web_adapter refactoring: funziona per demo |
| #93 | **fix-pre-MVP** | ValueError su all-None prices: 1 riga di fix (`min(..., default=1.0)`) |
| #94 | **post-MVP** | Test coverage gaps: non bloccano demo |
| #95 | **post-MVP** | DB migrations/health checks: non servono per demo locale |
