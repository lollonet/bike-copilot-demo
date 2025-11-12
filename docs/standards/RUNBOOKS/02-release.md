---
title: Runbook — Rilascio e Rollback
---

Rilascio
- Assicurati che main sia verde
- Tag: `git tag -a vX.Y.Z -m "REQ-###: summary" && git push origin vX.Y.Z`
- File note con i cambi; pubblica: `gh release create vX.Y.Z -t "vX.Y.Z" -F notes.md`
- Imposta come Latest: `gh release edit vX.Y.Z --latest`

Rollback
- Crea vX.Y.Z+hotfix oppure re‑imposta Latest a un tag precedente
- Documenta un ADR se il rollback è dovuto a cambio di design
