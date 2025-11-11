---
title: Release & Rollback Runbook
---

Release
- Ensure main is green
- Tag: `git tag -a vX.Y.Z -m "REQ-###: summary" && git push origin vX.Y.Z`
- Notes file with changes; publish: `gh release create vX.Y.Z -t "vX.Y.Z" -F notes.md`
- Pin as Latest: `gh release edit vX.Y.Z --latest`

Rollback
- Create vX.Y.Z+hotfix or re-point Latest to a previous tag
- Document ADR if rollback due to design change

