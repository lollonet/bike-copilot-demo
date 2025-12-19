# /review — Code Review (SOTA)

$ARGUMENTS

## Scope

- If files/PR are specified in `$ARGUMENTS`, review only those.
- Otherwise review the working tree changes (`git diff`) or the last commit, depending on context.

## Checklist

- Correctness + edge cases
- Error handling (I/O, parsing, retries)
- Type safety (avoid `Any`/casts/ignores unless justified)
- Security (secrets/state, injection, unsafe file ops)
- Performance regressions
- Tests: missing coverage for changed behavior
- Docs: update if user-facing behavior changes

## Output

Use `CORE.md` standard sections:

Analisi:
Piano:
Patch:
Test:
Note:

In `Analisi`, list findings grouped by severity (CRITICAL/HIGH/MEDIUM/LOW) with `file:line` when possible.

