# /audit — Codebase Audit (SOTA)

**Usage**: `/audit [quick|deep|idiomatic] [scope]`

$ARGUMENTS

## Principles (implementation-first)

- Prefer evidence from imports/call paths and tests.
- Distinguish clearly between **defined** vs **used** code.
- Only ask blocking questions (max 3); otherwise proceed with explicit assumptions.

## Modes

- `quick` (default): top issues + obvious dead/duplicate code candidates
- `deep`: broader architecture review (boundaries, coupling, testability, reliability)
- `idiomatic`: compare patterns against installed dependencies in `.venv/`

## Output

Use `CORE.md` standard sections:
Analisi:
Piano:
Patch:
Test:
Note:

For `quick/deep/idiomatic`, include:
- Top findings with evidence (file paths)
- Suggested simplification roadmap (small, atomic steps)

