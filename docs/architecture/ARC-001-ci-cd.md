---
id: ARC-001
domain: architecture
status: approved
source_of_truth: false
related: [ARC-INDEX, REQ-001]
---
CI/CD — Overview and Gates

Pipeline (GitHub Actions)
- Workflow: .github/workflows/ci.yml (name: CI)
- Triggers: push (all branches), pull_request
- Steps (order):
  1) Checkout repository
  2) Setup Python 3.11
  3) Setup uv and sync deps (`uv sync`)
  4) Complexity Gate (repo‑wide): `uv run python scripts/complexity_gate.py`
  5) Spec Lint + Traceability: `uv run python scripts/spec_lint.py && uv run python scripts/traceability.py`
  6) Tests (if tests/ exists): `uv run pytest -q`
  7) Upload artifact: `traceability/matrix.yaml`

Gates
- Complexity thresholds defined in CONTROL.yaml (mccabe/cognitive/LOC). Failing thresholds should fail the job.
- Docs spec lint/traceability must pass.
- Tests are executed when present.

Local Parity
- Use `make status` for ruff/format/types and `make test` for tests.
- Docs runbook 05 aligns docs/ with CI and CONTROL.yaml.

