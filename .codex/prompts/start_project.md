# /start_project — Bootstrap a Project (SOTA)

$ARGUMENTS

## Goal

Generate a small, opinionated project skeleton aligned with `CORE.md`.

## Defaults

- Prefer **uv** for dependency management.
- Prefer **ruff + mypy/basedpyright + pytest** gates.
- Keep configuration in one place; avoid duplicated settings.

## Templates

This repo contains starting points in `templates/`:

- `templates/backend/` (infra scaffolding: Dockerfile/Makefile/CI snippets)

For more detailed scaffolding guidance, see `runbook/start_project.md`.

If you need a full Python package layout (src/, tests/, etc.), create it explicitly and keep it minimal.

## Output

Respond with:
Analisi:
Piano:
Patch:
Test:
Note:

Ask up to **3** blocking questions only if required (e.g., backend vs cli vs library, package name, Python version).
