---
title: Sistema Documentale — Panoramica
---

Tassonomia
- Requisiti (REQ-###): funzionali o non funzionali con criteri di accettazione. Indice: `docs/requirements/REQ-INDEX.md`.
- Architettura (ARC-###): elementi e contesti architetturali. Indice: `docs/architecture/ARC-INDEX.md`.
- Tecnologia (TECH-###): runtime/policy e ambiente. Indice: `docs/technology/TECH-INDEX.md`.
- ADR (ADR-###): Architecture Decision Records.
- Standard/Runbook: guide procedurali e stile. Non fanno parte della tassonomia REQ/ARC/TECH/ADR.

Front matter
- Campi obbligatori: `id`, `domain`, `status`, `source_of_truth`, opzionale `related`. I REQ includono anche `acceptance`.

Tracciabilità
- Gli ID REQ nel repo alimentano `traceability/matrix.yaml` via `scripts/traceability.py`.
- Lo script esclude directory generate e la matrice stessa per evitare auto‑riferimenti.

Gate
- `scripts/spec_lint.py` valida ID, domini e acceptance dei REQ.
- I messaggi di commit devono includere `REQ-###` (hook `.githooks/commit-msg`).
- La CI esegue: complexity gate → spec lint → traceability → test via uv (pytest opzionale).
- Complexity gate (repo‑wide):
  - McCabe e function LOC via `uvx radon` (output JSON).
  - Cognitive complexity via `uvx flake8 --with flake8-cognitive-complexity` (CCR).
  - Soglie lette da `CONTROL.yaml`.

Copertura
- Fase 1 osservazione; obiettivi finali: line 85%, branch 85%.

Type checking
- `scripts/status.sh` esegue basedpyright su `app` e/o `scripts` quando presenti.

Come aggiungere un documento
1) Crea il doc con front matter valido.
2) Referenzia gli ID correlati dove opportuno.
3) Esegui `uv run python scripts/spec_lint.py`.
4) Commit con `REQ-###` nel messaggio; apri una PR.
