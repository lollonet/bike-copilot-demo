# /refactor — Systematic Refactor (SOTA)

## Entry Point

$ARGUMENTS

## Goals

- Improve structure/maintainability **without changing behavior**, unless explicitly requested.
- Keep diffs small and reversible; remove dead code when safe.
- Enforce `CORE.md` rules: minimal diffs, one clear path, max 3 blocking questions.

## Process

1. **Scope + invariants**
   - Identify the exact code paths involved (imports/call sites).
   - Define what must not change (public API, CLI flags, file formats, etc.).

2. **Plan**
   - Break into atomic steps with verification after each.
   - Prefer extracting helpers over introducing new abstractions.

3. **Implement**
   - Apply changes incrementally.
   - Keep typing boundaries explicit (no `Any`/casts/ignores unless justified).

4. **Verify**
   - Run the available gates (format/lint/typecheck/tests).

## Output

Always respond with:
Analisi:
Piano:
Patch:
Test:
Note:

If blocked, ask up to **3** questions; otherwise proceed with explicit assumptions.

