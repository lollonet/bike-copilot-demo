---
title: Operator Quickstart
---

Goal: minimal steps to work on this repo.

Setup
- Install deps: `uv sync`
- Enable repo hooks (one-time per clone):
  - `git config core.hooksPath .githooks`
  - Verify: `git config --local --get core.hooksPath` should print `.githooks`

Daily
- Check: `bash scripts/status.sh` (use `--fix` to apply)
- Run tools:
  - Spec lint: `uv run python scripts/spec_lint.py`
  - Traceability: `uv run python scripts/traceability.py`
- Implement changes; keep diffs small and typed
- Commit: include `REQ-###` in the message
- Push; open PR; ensure CI is green

Release (summary)
- Tag: `git tag -a vX.Y.Z -m "REQ-###: summary" && git push origin vX.Y.Z`
- Release: `gh release create vX.Y.Z -t "vX.Y.Z" -F <notes.md>`

Optional: shell completions
- Bash: `source scripts/completions/adopt_standards.bash && source scripts/completions/status.bash`
- Zsh: `autoload -Uz compinit && compinit; fpath+=("$(pwd)/scripts/completions"); autoload -Uz adopt_standards status`

Notes
- Type check (status.sh) runs on `src` and/or `scripts` when present.
- Tests run via `uv run pytest` if a test suite exists.
