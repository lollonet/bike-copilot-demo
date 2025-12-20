project: Bike Sourcing Copilot
session: 2025-11-10
facilitator: "IT Partner"
participants: [ "Negoziante", "Dev" ]

status: archived
---

# SESSION SUMMARY — 2025-11-10

## Decisioni
- Confermato MVP **locale** su Mint: Python + SQLite + Streamlit + reportlab.
- CSV demo come unica fonte, compatibilità con regole deterministiche + sinonimi.
- KPI MVP: preventivo ≤60s, ≥95% richieste con proposta.

## Rischi & Mitigazioni
- CSV incompleti → validazioni e default; log WARN per righe scartate.
- Dedup senza EAN → soglia conservativa su brand+MPN.

## Prossime azioni (owner → due date)
- **T1 Modelli & DB** (`Dev`) → 2025‑11‑11  
- **T3 Ingest CSV** (`Dev`) → 2025‑11‑11  
- **T6 Search + Ranking** (`Dev`) → 2025‑11‑12  
- **T7 PDF** (`Dev`) → 2025‑11‑12  
- **T8 UI E2E** (`Dev`) → 2025‑11‑13  
- **Deploy Mint + systemd** (`IT Partner`) → 2025‑11‑13

## Materiali allegati
- `VISION.md` v1.0 (frozen)
- `ARCH.md` v1.0 (frozen)
- `TECH.md` v1.0 (review)
- `DIFF-2025-11-10.md` (frozen)

## Metriche da raccogliere in demo
- Tempo da input a PDF, % in‑stock nella top‑3, tasso errori compatibilità segnalati.
```


