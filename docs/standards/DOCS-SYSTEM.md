---
title: Docs System Overview
---

Taxonomy
- Requirements (REQ-###): functional or non-functional requirements with acceptance criteria. Index: `docs/requirements/REQ-INDEX.md`.
- Architecture (ARC-###): architectural elements and contexts. Index: `docs/architecture/ARC-INDEX.md`.
- Technology (TECH-###): runtime/policy and environment. Index: `docs/technology/TECH-INDEX.md`.
- ADR (ADR-###): Architecture Decision Records.
- Standards/Runbooks: procedural guides and style. Not part of the REQ/ARC/TECH/ADR taxonomy.

Front matter
- Required fields: `id`, `domain`, `status`, `source_of_truth`, optional `related`. REQ docs also include `acceptance`.

Traceability
- REQ IDs discovered across the repo feed `traceability/matrix.yaml` via `scripts/traceability.py`.
- The script excludes generated directories and the matrix output itself to avoid self-references.

Gates
- `scripts/spec_lint.py` validates IDs, domains, and REQ acceptance.
- Commit messages must include `REQ-###` (enforced by `.githooks/commit-msg`).
- CI runs: complexity gate → spec lint → traceability → tests using uv (pytest optional).
- Complexity gate (repo-wide):
  - McCabe and function LOC via `uvx radon` (JSON output).
  - Cognitive complexity via `uvx flake8 --with flake8-cognitive-complexity` (CCR).
  - Thresholds read from `CONTROL.yaml`.

Coverage
- Phase 1 observe-only; end‑state targets: line 85%, branch 85%.

Type checking
- `scripts/status.sh` runs basedpyright on `src` and/or `scripts` when present.

How to add a new item
1) Create the doc with valid front matter.
2) Reference related IDs where applicable.
3) Run `uv run python scripts/spec_lint.py`.
4) Commit with `REQ-###` in the message; open a PR.
