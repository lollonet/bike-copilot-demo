---
id: REBOOT-02
domain: docs
status: draft
---

# 02 — Technical Debt & Risk Assessment

## Debito per Surface Area

### A. Integration Fragility (ALTO)
| Item | Evidenza | Impact MVP | Decision |
|------|----------|------------|----------|
| Credenziali B2B scadute | `.env` contiene password settate mesi fa | **blocca** | fix-ora |
| DOM portali cambiato | `providers/mappings/*.yaml` con selettori CSS | **blocca** (se rotti) | fix-ora (verificare) |
| Login flow cambiato | `service_helpers.py:278,381` — SPA/form login | **blocca** (se rotto) | fix-ora (verificare) |
| Anti-bot aggiornato | Playwright stealth potrebbe non bastare | **blocca** (se rilevato) | fix-ora (verificare) |

### B. Parser/Selector Drift (MEDIO)
| Item | Evidenza | Impact MVP | Decision |
|------|----------|------------|----------|
| Selettori CSS montanini | `providers/mappings/montanini_mapping.yaml` | rallenta | verificare durante T3 |
| Selettori CSS ciclodiffusione | `providers/mappings/ciclodiffusione_mapping.yaml` | rallenta | verificare durante T3 |
| Selettori CSS ciclopromo | `providers/mappings/ciclopromo_mapping.yaml` | rallenta | verificare durante T3 |
| Selettori CSS rms | `providers/mappings/rms_mapping.yaml` | rallenta | verificare durante T3 |

### C. Branch Divergence (BASSO)
| Item | Evidenza | Impact MVP | Decision |
|------|----------|------------|----------|
| 4 PR non mergiate da mesi | PR #85-#88 | rallenta | merge-as-is/rebase (vedi 00_state) |
| 5 branch stale | claude-refactor, feat/docs-refactor-gemini, etc. | cosmetico | defer (pulire post-MVP) |
| Uncommitted changes | web_adapter.py, test_fetch_timeout.py su fix/log-002 | rallenta | fix-ora (commit/stash) |
| 2 stash entries | WIP skeptic + pre-merge | cosmetico | defer |

### D. Operational Setup (MEDIO)
| Item | Evidenza | Impact MVP | Decision |
|------|----------|------------|----------|
| wkhtmltopdf non installato | `which wkhtmltopdf` → exit 1 | cosmetico (HTML fallback) | defer (nice-to-have) |
| Playwright browsers | Potrebbe servire `playwright install chromium` | rallenta | fix-ora (T0) |
| uv.lock freshness | Aggiornato Gen 2026, potrebbe servire `uv sync` | rallenta | fix-ora (T0) |

### E. Fixture-vs-Reality Gap (MEDIO)
| Item | Evidenza | Impact MVP | Decision |
|------|----------|------------|----------|
| 199 test su fixture sintetiche | `tests/` — nessun test con dati reali | rallenta | accept (test manuali durante T4-T5) |
| DB con dati demo | `app.db` 1.7MB — solo seed data | rallenta | fix-ora (reset-db + ingest reale) |
| BIZ-001: ValueError su all-None prices | `app/search.py:247` — `min()` senza default | **blocca** (edge case) | fix-ora (1 riga) |

### Nota sulla Static Cleanliness
Zero lint errors (ruff), zero type errors (basedpyright), 199 test passano. Questo e' un **segnale debole positivo**: il codice e' pulito staticamente ma NON prova che le integrazioni esterne funzionino. Il vero rischio e' runtime, non statico.

---

## Rischi Specifici del Reboot

| Rischio | Probabilita' | Impact | Mitigazione |
|---------|-------------|--------|-------------|
| Credenziali scadute | **Alta** | Blocca tutto | Verificare + rinnovare prima di qualsiasi test |
| DOM portali cambiato | **Media** | Blocca scraping | Verificare manualmente 1 pagina per fornitore |
| PR merge causa regressione | **Bassa** | Rallenta | Cascade analysis fatta (vedi 00_state), re-test post-merge |
| Playwright browsers outdated | **Media** | Rallenta | `playwright install chromium` in T0 |
| Dati demo insufficienti | **Bassa** | Rallenta | `make reset-db` + ingest reale |
| Issues #89-#95 distraggono | **Media** | Rallenta | Tutti post-MVP per decisione esplicita |
