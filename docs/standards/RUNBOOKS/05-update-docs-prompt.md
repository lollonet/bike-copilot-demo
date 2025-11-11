---
title: Prompt — Update docs/ after adoption
---

Paste‑This Prompt for Codepilot

You are Codepilot working locally in this repository. Update the docs/ directory so it accurately reflects the current codebase after a fresh adoption of the paradigm. Follow these instructions exactly.

Context and Goals
- Goal: Bring docs/ into sync with the current codebase and CI gates, without inventing functionality.
- Scope: docs/, docs/index.yaml, docs/requirements/, docs/architecture/, docs/technology/, docs/adr/, standards/runbooks; do not touch application logic.
- Language: English only. Keep docs concise and non-duplicative. Use front‑matter where required.

Authoritative Inputs (read first, don’t guess)
- AGENTS.md (playbook and rules)
- CONTROL.yaml (coverage phase, complexity thresholds, analysis paths)
- .github/workflows/ci.yml (actual CI steps and order)
- README.md (operator-facing guidance)
- scripts/ (status, spec_lint, traceability, complexity, adoption)
- docs/index.yaml (indices map); existing docs under docs/

Strict Constraints
- Do not remove existing accepted requirements; add/adjust only as needed to reflect reality.
- Use valid front‑matter for REQ/ARC/TECH/ADR where applicable:
  - Required: id, domain, status, source_of_truth; REQ also needs acceptance[].
- Keep Single Sources of Truth: indices (REQ‑INDEX, ARC‑INDEX, TECH‑INDEX) must reference what actually exists.
- No duplication: if a detail is defined elsewhere (CI, scripts, CONTROL), link or summarize; don’t restate exhaustively.
- English, concise, actionable. No placeholders left.

Deliverables (what to produce/adjust)
1) Indices and map
- Ensure docs/index.yaml exists and points to REQ‑INDEX, ARC‑INDEX, TECH‑INDEX, ADR dir, and Standards hub.
- Ensure those INDEX docs exist and accurately describe how IDs are structured.

2) Requirements and adoption anchor
- Ensure a “standards adoption” REQ (e.g., REQ‑010) exists with acceptance that matches the actual gates/tools (hooks enabled, spec_lint, traceability, CI complexity gate, tests runner).
- Do not fabricate feature requirements; only document process/infra requirements if missing.

3) Architecture and technology
- Architecture (ARC): add or update a brief CI/CD design doc that matches .github/workflows/ci.yml (order of gates, artifacts). If it exists, sync it.
- Technology (TECH): if a runtime/environment doc exists, ensure it mentions the current tooling posture at a high level without duplicating operational how‑tos already in README/runbooks.

4) ADR folder
- Ensure docs/adr/ exists. If no ADRs exist, keep the directory (with .keep) referenced by index; do not invent decisions.

5) Standards/runbooks
- If present, ensure quickstart/adoption runbooks reflect current commands (status script, spec/traceability/complexity runners, test runner).
- Keep these procedural and concise; avoid duplicating the INDEX or TECH/ARC content.

Acceptance Checks (must pass)
- Indices are consistent and resolvable; no dead links.
- spec_lint passes (no missing id/domain/acceptance in REQs).
- traceability matrix regenerates cleanly (no self‑references, no fabricated IDs).
- Docs reference the actual CI gates and CONTROL thresholds at a high level (no contradictions).
- English; no placeholders left.

Plan (execute step‑by‑step; show a short preamble before each tool call)
1) Inventory
- Read AGENTS.md, CONTROL.yaml, .github/workflows/ci.yml, scripts/, README.md, docs/index.yaml.
- List mismatches: missing index/docs, CI order vs docs, missing ADR dir, missing adoption REQ.

2) Propose minimal doc deltas
- Draft a short patch plan: which files to add/update and why (bullet list, max 8 items).

3) Apply patches
- Create/update:
  - docs/index.yaml if missing or incomplete
  - REQ‑010 (standards adoption) if missing, with precise acceptance reflecting current gates
  - ARC CI/CD doc (update steps order to match workflow)
  - TECH runtime (only if it exists or is required; keep high level)
  - Create docs/adr/.keep if folder is absent, but do not invent ADR content
- Keep edits minimal and non‑duplicative.

4) Validate
- Run:
  - uv run python scripts/spec_lint.py
  - uv run python scripts/traceability.py
- If issues, fix docs until passing.

5) Summarize and handoff
- Output a concise list of changed files and the rationale (bullets).
- Confirm acceptance checks passed.

Ground Rules
- No external web access. Use only files present in the repo.
- Do not change code or CI behavior; document what exists.
- Prefer links/paths to existing files over copying content into multiple docs.
- Keep each doc short: context, what matters, where to go next.

Commit Guidance
- Use a REQ tag already present (e.g., REQ‑010) in the commit message.
- Example: “REQ‑010: sync docs with CI gates and CONTROL; add adoption requirement; fix indices.”

