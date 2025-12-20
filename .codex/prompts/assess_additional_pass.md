# /assess_additional_pass — Second Pass (SOTA)

$ARGUMENTS

## Goal

Improve the previous assessment by tightening evidence, expanding coverage, and removing assumptions.

## Checklist

- Add concrete evidence for every major claim (file paths; `file:line` when feasible).
- Identify any missed subsystems or integration points; explicitly state what was *not* reviewed.
- Convert “should” statements into observed facts + impact + remediation.
- Re-check risks: security, correctness, performance, maintainability.
- Produce a short, prioritized roadmap of simplifications (small, atomic steps).

## Output

Use `CORE.md` standard sections:
Analisi:
Piano:
Patch:
Test:
Note:

If blocked, ask up to **3** questions; otherwise proceed with explicit assumptions.
