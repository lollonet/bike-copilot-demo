---
id: ARC-001
domain: architecture
status: approved
source_of_truth: false
related: [ARC-INDEX, REQ-001]
---
CI/CD — Panoramica e Gate

Pipeline (GitHub Actions)
- Workflow: .github/workflows/ci.yml (name: CI)
- Trigger: push (tutti i branch), pull_request
- Passi (ordine):
  1) Checkout repository
  2) Setup Python 3.11
  3) Setup uv e sincronizzazione dipendenze (`uv sync`)
  4) Complexity Gate (repo‑wide): `uv run python scripts/complexity_gate.py`
  5) Spec Lint + Traceability: `uv run python scripts/spec_lint.py && uv run python scripts/traceability.py`
  6) Test (se esiste tests/): `uv run pytest -q`
  7) Upload artefatto: `traceability/matrix.yaml`

Gate
- Soglie di complessità definite in CONTROL.yaml (mccabe/cognitive/LOC). Se superate, il job fallisce.
- Spec lint/traceability devono passare.
- I test vengono eseguiti quando presenti.

Parità locale
- Usa `make status` per ruff/format/type e `make test` per i test.
- Il runbook 05 allinea i docs con CI e CONTROL.yaml.
