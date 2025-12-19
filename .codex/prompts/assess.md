# /assess — Architecture Assessment (SOTA)

$ARGUMENTS

## Goal

Produce an evidence-based assessment of the codebase architecture focusing on **what is actually used** (imports/call paths/tests), not only what exists on disk.

## Approach

- Identify entry points and active code paths.
- Distinguish **defined vs used** code; list dead/duplicate candidates.
- Evaluate boundaries (config, I/O, domain logic, adapters) and coupling.
- Flag risks: security, correctness, performance, maintainability.
- Propose simplifications as small, atomic steps (one clear path).

## Output

Use `CORE.md` standard sections:
Analisi:
Piano:
Patch:
Test:
Note:

If no code changes are requested, keep `Patch/Test` as N/A and focus on findings + roadmap.
