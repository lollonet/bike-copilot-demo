Style, security, naming, formatting, and lint guidelines.

Principles
- Prefer clear, explicit code over cleverness.
- Strong typing at boundaries (see AGENTS.md): no Any, no casts.
- One path per behavior; delete duplicates.

Python
- Use uv-managed env: `uv run`, `uvx` for tools.
- Lint: `ruff`; Format: `ruff format`; Types: `basedpyright`.
- No broad exceptions; no reflection for control flow.

Docs
- Every REQ has acceptance criteria and consistent ID prefix.
- Keep indices up to date; run spec lint before committing.

Complexity
- Targets (repo-wide): McCabe warn 8 / fail 12; function LOC warn 25 / fail 30; cognitive complexity warn 12 / fail 15.
- Measurement: `scripts/complexity_gate.py` using radon (McCabe + LOC) and flake8-cognitive-complexity (CCR) via CLI.
- Policy source: `CONTROL.yaml` (no extra tool configs; thresholds enforced in CI).
 - Guidance: functions exceeding 30 LOC or high complexity should be refactored into smaller units with clear responsibilities.

Type Safety
- basedpyright runs over `src` and/or `scripts` (when present) via `scripts/status.sh`.
