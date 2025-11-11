# Engineering Charter (Agent Playbook)

Global Rules (non‑negotiable)
- Read sources in order: requirements → architecture → technology → standards → ADR.
- Only act when every change traces back to an approved `REQ-###`.
- Required flow: READ → PLAN → PATCH → TEST → LOG.

Allowed Commands (mental model)
- READ(ID|path): cite relevant sections before acting.
- PLAN(change): patch plan (files, functions, tests) mapped to REQ/ADR.
- PATCH(file,diff): atomic unified diff, aligned to the PLAN.
- TEST(list): create/update tests mapped to REQ-###.
- LOG(note): write a session note under `.codepilot/sessions/<id>.md`.

Bans
- No code without an associated REQ.
- No duplicated information across documents (no‑overlap).
- If sources diverge, stop and propose an ADR or issue.

Docs System (authoritative)
- Taxonomy:
  - Requirements (`REQ-###`): have `acceptance` criteria. Index: `docs/requirements/REQ-INDEX.md`.
  - Architecture (`ARC-###`): elements and contexts. Index: `docs/architecture/ARC-INDEX.md`.
  - Technology (`TECH-###`): runtime/policy. Index: `docs/technology/TECH-INDEX.md`.
  - ADR (`ADR-###`): decision records under `docs/adr/`.
  - Standards/Runbooks: procedures and style under `docs/standards/` (not part of REQ/ARC/TECH/ADR taxonomy).
- Front matter schema:
  - Required: `id`, `domain`, `status`, `source_of_truth`.
  - Optional: `related` (list). REQ docs must include `acceptance`.
- Indices are the sources of truth per domain (REQ‑INDEX, ARC‑INDEX, TECH‑INDEX).
- No duplication: link between docs rather than restating content.

Tools and Gates
- Hooks: enable once per clone: `git config core.hooksPath .githooks`.
  - Commit messages must include `REQ-###` (or `INIT-000` for bootstrap).
- Lint/spec: `uv run python scripts/spec_lint.py`.
- Traceability matrix: `uv run python scripts/traceability.py`.
  - The script skips `traceability/matrix.yaml` and common generated dirs; output is `traceability/matrix.yaml`.
- Status (local gate): `bash scripts/status.sh` (use `--fix` to apply ruff fixes/format).
- Tests: `uv run pytest -q` (CI uses this; do not use `uvx pytest`).
- CI shape: checkout → setup‑python → setup‑uv → `uv sync` → spec‑lint + traceability → tests → upload matrix artifact.
- Releases: tag (`git tag -a vX.Y.Z … && git push origin vX.Y.Z`) and publish (`gh release create … && gh release edit … --latest`).

Command Cheatsheet
- Env setup: `uv sync`
- Hooks: `git config core.hooksPath .githooks`
- Spec lint: `uv run python scripts/spec_lint.py`
- Trace matrix: `uv run python scripts/traceability.py`
- Status: `bash scripts/status.sh [--fix]`
- Tests: `uv run pytest -q`
- Tag: `git tag -a vX.Y.Z -m "REQ-###: …" && git push origin vX.Y.Z`
- Release: `gh release create vX.Y.Z -t "vX.Y.Z" -F notes.md && gh release edit vX.Y.Z --latest`

Agent PR Checklist (docs & gates)
- Commit messages include a `REQ-###`; PLAN is visible; diffs are atomic.
- If behavior or contracts change, update REQ/ARC/TECH/ADR and their indices.
- Run `spec_lint` and fix issues; regenerate the traceability matrix.
- CI is green (spec lint, traceability, tests).
- Evidence is added to TECH docs when external libraries/providers are touched.

Pointers
- Quickstart: `docs/standards/RUNBOOKS/01-operator-quickstart.md`.
- Release runbook: `docs/standards/RUNBOOKS/02-release.md`.
- Docs system overview: `docs/standards/DOCS-SYSTEM.md`.
