---
id: REBOOT-06
domain: docs
status: draft
---

# 06 — Rollback & Safety Net

## Pre-Reboot Baseline

Eseguire PRIMA di qualsiasi modifica a main:

```bash
# 1. Tag baseline
git checkout main
git tag v0-pre-reboot

# 2. Snapshot DB
cp app.db app.db.pre-reboot

# 3. Backup env
cp .env .env.pre-reboot

# 4. Cattura versioni runtime
python3 --version > .runtime-baseline.txt
uv --version >> .runtime-baseline.txt
playwright --version >> .runtime-baseline.txt 2>/dev/null || echo "playwright: not installed" >> .runtime-baseline.txt

# 5. Test baseline
uv run pytest -v > test-baseline.txt 2>&1
echo "Expected: 199 collected, 193 passed, 6 skipped" >> test-baseline.txt

# 6. Quality baseline
uv run ruff check app/ tests/ >> test-baseline.txt 2>&1
uv run basedpyright app/ tests/ >> test-baseline.txt 2>&1
```

### Checklist Artefatti Locali

| Artefatto | Path | Azione pre-reboot |
|-----------|------|-------------------|
| Database | `app.db`, `app.db-shm`, `app.db-wal` | `cp app.db app.db.pre-reboot` |
| Env file | `.env` | `cp .env .env.pre-reboot` |
| Output dir | `out/` | Nessuna (rigenerabile) |
| Test DBs | `test_*.db` | Nessuna (rigenerabili) |
| Playwright cache | `~/.cache/ms-playwright/` | Annotare versione in .runtime-baseline.txt |
| Browser sessions | Nessun file persistente | N/A |
| Stash git | `stash@{0}`, `stash@{1}` | Lasciare (non toccare) |
| .agents/ | `.agents/runs/` | Nessuna (triad artifacts, non parte del codice) |

---

## Strategia Branch

```
main (v0-pre-reboot tag)
  │
  ├── reboot/t1-housekeeping     (merge PR, tag)
  ├── reboot/t2-credentials      (se serve fix .env)
  ├── reboot/t3-scraping-fix     (se serve fix selettori)
  ├── reboot/t4-search-fix       (BIZ-001 min default)
  ├── reboot/t5-optimizer-fix    (se serve)
  └── reboot/t6-demo-polish      (se serve)
```

- Ogni mini-triad su branch `reboot/tN-*`
- Merge in main solo dopo:
  1. `uv run pytest -v` passa
  2. `uv run ruff check app/ tests/` passa
  3. `uv run basedpyright app/ tests/` passa
  4. Verifica manuale della funzionalita' modificata
- NO merge diretto a main senza verifica

---

## Procedura di Rollback

### Rollback Parziale (ultimo mini-triad)

```bash
# Annullare l'ultimo merge (se non ancora pushato)
git revert HEAD --no-edit
uv run pytest -v  # verificare non-regressione
```

### Rollback Completo (tornare a pre-reboot)

```bash
# 1. Tornare al codice pre-reboot (NON distruttivo — crea nuovo branch)
git checkout v0-pre-reboot -b rollback-clean

# 2. Ripristinare DB
cp app.db.pre-reboot app.db

# 3. Ripristinare env
cp .env.pre-reboot .env

# 4. Verificare
uv run pytest -v
# Deve matchare test-baseline.txt (199 collected, 193 passed, 6 skipped)
```

### Se main e' gia stato pushato con reboot changes

```bash
# NON usare git reset --hard (distruttivo)
# Invece: revert tutti i commit post-tag
git log --oneline v0-pre-reboot..main  # mostra commit da revertare
git revert --no-edit v0-pre-reboot..HEAD  # revert sequenziale
git push  # push dei revert
```

---

## Verifica Non-Regressione

Dopo OGNI merge in main durante il reboot:

```bash
# Quality gates (devono tutti passare)
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/
uv run basedpyright app/ tests/
uv run pytest -v --tb=short tests/

# Conteggio test non deve diminuire
# Baseline: 199 collected, 193 passed, 6 skipped
```

Se il conteggio test diminuisce o i gate falliscono: **STOP, non mergare, investigare**.
