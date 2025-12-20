---
id: ARC-001
domain: architecture
status: approved
source_of_truth: false
related: [ARC-INDEX, REQ-001]
---
# ARC-001: CI/CD Pipeline & Workflow

## Overview
La pipeline CI/CD è progettata per garantire la qualità del codice (SOTA) attraverso molteplici gate automatici, sia locali che remoti.

## 🛠️ Local Workflow (Development)
Lo sviluppatore utilizza il `Makefile` standardizzato per verificare il codice prima del push.

### Comandi Principali
- `make status`: Esegue Linting (Ruff) e Formatting.
- `make test`: Esegue la suite di test standard (escludendo `_legacy`).
- `make ci-fast`: **Gatekeeper Locale**. Esegue Lint + Typecheck + Fast Tests. Deve passare prima di ogni push.
- `make ci-sota`: Full Verification. Esegue `ci-fast` + Security + Complexity + Traceability.

### Git Hooks (Governance)
- **pre-push**: Blocca i push diretti su `main` e forza l'esecuzione di `make ci-fast`. Se il check locale fallisce, il push viene abortito.

## 🔄 GitHub Actions (Remote CI)

### 1. Main CI (`ci.yml`)
Esegue la validazione completa su ogni Push e Pull Request.
- **Lint & Typecheck**: Ruff, Basedpyright.
- **Complexity Gate**: Analisi ciclomatica e cognitiva (soglie in `CONTROL.yaml`).
- **Security**: Bandit scan.
- **Traceability**: Verifica copertura requisiti (`matrix.yaml`).
- **Tests**: Esecuzione suite pytest.

### 2. Fast Feedback (`ci-fast-feedback.yml`)
Esegue un check rapido (`make ci-fast`) su ogni commit e commenta sulla PR **solo in caso di fallimento**.
- Trigger manuale: `@ci review` nei commenti.

### 3. AI Code Review (`claude-code-review.yml`)
Analisi qualitativa del codice tramite Claude 3.5 Sonnet.
- Trigger automatico: Apertura/Sync PR.
- Trigger manuale: `@claude review` nei commenti.

### 4. Documentation Automation (`update-session-log.yml`)
Aggiorna automaticamente il registro delle attività al merge delle PR.
- Target: `docs/summaries/pr/YYYY-MM-DD-pr-log.md`.

## 📦 Artifacts
- `traceability/matrix.yaml`: Matrice di tracciabilità requisiti.
- `complexity-report`: Report dettagliato della complessità del codice.