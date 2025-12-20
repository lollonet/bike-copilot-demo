# /idiomatic_assessment — Dependency-Idiomatic Audit (SOTA)

$ARGUMENTS

## Goal

Assess how closely the codebase follows the idioms of its **installed dependencies** (runtime truth in `.venv/`), and propose simplifications to reduce divergence and maintenance cost.

## Approach

- Identify the key dependencies and their intended usage patterns from installed code.
- Compare the project’s usage patterns to those idioms (imports, call sites, configuration).
- Highlight deviations with impact and recommend a consistent “one clear path”.

## Output

Use `CORE.md` standard sections:
Analisi:
Piano:
Patch:
Test:
Note:

In `Note`, include evidence sources (paths under `.venv/` and any official docs if used) and a confidence level.

