---
title: Session Summary Workflow
---

Purpose
- Keep a concise, instruction-only summary per work session to reduce onboarding time after context switches.

Template
- Session summaries are created under `.codepilot/sessions/`.
- Use the helper script to generate prefilled templates.

Helper script
- Generate a prefilled summary with current metadata:
  - `bash scripts/new_session_summary.sh [--project NAME] [--author NAME] [--status VALUE]`
- Options:
  - `--project` overrides repo name
  - `--author` sets the author field
  - `--status` sets the status (default `active`)
  - `--dry-run` prints to stdout instead of writing

Output
- Creates `.codepilot/sessions/SESSION-<YYYYMMDD><shortsha>.md` with:
  - Front matter (project, session_date, author, status)
  - Prefilled metadata (branch, latest commit, timestamp)
  - Generic sections to fill (context, last session, focus, queue, references, at-a-glance, resume, decisions, changelog, briefing, closeout)

Tips
- Keep bullets one line each; mark unknowns as `(unknown)`.
- Link key PRs/issues in “Repo & CI At‑a‑Glance”.
- Save at session start and update at closeout.
