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
- Trigger: push (all branches), pull_request
- Steps (order):
  1) Checkout repository (actions/checkout@v4)
  2) Setup Python 3.11 (actions/setup-python@v5)
  3) Setup uv and sync dependencies (`uv sync`)
  4) Complexity Gate (repo-wide): `uv run python scripts/complexity_gate.py --paths src scripts`
  5) Complexity (observe app): `uv run python scripts/complexity_gate.py --paths app` (continue-on-error)
  6) Upload complexity-app report artifact
  7) Spec Lint + Traceability: `uv run python scripts/spec_lint.py && uv run python scripts/traceability.py`
  8) Test (if tests/ or pytest.ini exists): `uv run pytest -q || true` (non-failing)
  9) Upload artifact: `traceability/matrix.yaml`

Gates
- Complexity thresholds defined in CONTROL.yaml (mccabe/cognitive/LOC). If exceeded, job fails.
- Spec lint/traceability must pass.
- Tests run when present (non-failing for observation).

Parità locale
- Usa `make status` per ruff/format/type e `make test` per i test.
- Il runbook 05 allinea i docs con CI e CONTROL.yaml.
