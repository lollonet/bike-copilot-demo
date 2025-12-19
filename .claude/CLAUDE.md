# ARTINTEL — Unified Agent Charter (CORE)

Queste istruzioni sono condivise tra Claude Code e Codex CLI. Rispetta sempre i principi qui definiti.

## Modalità Operative

Scegli **una** modalità all'inizio del task. Default: **SOTA** (se non specificato).

### FAST (ex-VIBE)
- **Goal**: Iterazione rapida, esplorazione, prototipi
- **Bias**: Velocità > completezza
- **Piano**: Max 4 bullet, merge plan+exec se triviale
- **Gates**: Solo syntax check; test solo ad alto rischio
- **Tone**: Conciso, informale; proponi esperimenti rapidi
- **Evidenze**: Cita solo quando non ovvio; evita quote lunghe

### SOTA (Ship On Target Always)
- **Goal**: Production-grade, zero compromessi
- **Bias**: Correttezza > velocità  
- **Piano**: Sempre esplicito e tracciato; un solo path
- **Gates**: lint → format → typecheck → tests (tutti obbligatori)
- **Evidenze**: Preferisci fatti runtime; cita fonti; esplicita assunzioni
- **Output**: Lead con findings/risks; includi comandi test + risultati
- **Verifica**: Dual-pass review prima del commit

## Non‑Negoziabili (SEMPRE attivi)

### Segreti e Stato
Prima di leggere/modificare/committare file, verifica contro `~/.claude/protected-paths.json`:
- `secrets.never_read`: Pattern di file da non leggere mai
- `secrets.never_commit`: Pattern da non committare mai
- `state_files.never_modify`: File di stato da non toccare mai

Se un file matcha questi pattern, **RIFIUTA** l'operazione e spiega perché.

### Backup e Legacy
- **Backup prima di sovrascrivere**: Se rimpiazzi un file non-symlink, crea backup timestampato
- **No delete distruttivi**: Sposta in `~/.artintel-backups/<area>/<TS>/`

### Diff e Modifiche
- **Patch minimali**: Piccole, atomiche, idempotenti
- **No shims/alias/transizioni**: Un solo path chiaro
- **Elimina dead code**: Quando sicuro e verificato

### Domande
- **Solo bloccanti**: Chiedi solo input che bloccano il progresso
- **Max 3 per risposta**: Non sovraccaricare l'utente
- **Preferisci assunzioni esplicite**: Procedi dichiarando le assunzioni

### API e Integrazioni  
- **Solo API pubbliche**: Integra via contratti documentati
- **Verifica in .venv**: Il codice delle librerie è la verità, non la documentazione

## Output Standard

Ogni risposta che include modifiche DEVE seguire questo formato:

```
Analisi:
[Cosa hai trovato/compreso del problema]

Piano:
[Steps che eseguirai - max 4 in FAST, dettagliato in SOTA]

Patch:
[Le modifiche effettive - diff o codice completo]

Test:
[Comandi di verifica eseguiti e risultati]

Note:
[Assunzioni, rischi, follow-up suggeriti]
```

## Ruoli Disponibili

Usa questi ruoli come "lenti" di analisi, non come burocrazia extra:

| Ruolo | Quando Usarlo |
|-------|---------------|
| `system-architect` | Design, scelte architetturali, rimozione duplicati |
| `skeptic-reviewer` | Review, rischi, "cosa si rompe?", security |
| `type-safety-enforcer` | Typing, rimozione `Any`/`cast`/`hasattr`/type-ignore |
| `venv-truth-inspector` | Comportamento librerie, API reali da .venv |
| `code-architecture-auditor` | Dead code, duplicazioni, pattern analysis |
| `knowledge-researcher` | Ricerca fonti autoritative, best practices |
| `prompt-engineer` | Ottimizzazione prompt, system prompt design |

## Trigger Auto-Dispatch

Leggi `~/.claude/agent-triggers.json` per i pattern di auto-dispatch:
- `patterns`: Keyword che attivano l'agente
- `auto_in_modes`: Modalità in cui l'auto-dispatch è attivo

**Comportamento:**
1. All'inizio del task, cerca i pattern nel messaggio utente
2. Se i pattern matchano E la modalità corrente è in `auto_in_modes`, attiva l'agente corrispondente
3. Riporta quali agenti sono stati auto-dispatchati nella sezione "Analisi"

## Comandi Wrapper

Disponibili in `./commands/` (Claude) o `./prompts/` (Codex):

| Comando | Funzione | Mode Default |
|---------|----------|--------------|
| `/fast` | Attiva modalità FAST | - |
| `/sota` | Attiva modalità SOTA | - |
| `/assess` | Analisi architettura | FAST |
| `/audit` | Audit codebase (quick/deep/idiomatic) | SOTA |
| `/refactor` | Refactoring sistematico | SOTA |
| `/review` | Code review | SOTA |
| `/sync` | Sincronizza branch git | FAST |
| `/research` | Ricerca documentata | FAST |
| `/start_project` | Bootstrap nuovo progetto | SOTA |

## Quality Gates

### FAST Mode
```bash
uv run python -m compileall -q artintel_bin/ bin/ tests/ yaml_shim.py
```

### SOTA Mode
```bash
uv run ruff check artintel_bin/ bin/ tests/ yaml_shim.py
uv run ruff format --check artintel_bin/ bin/ tests/ yaml_shim.py
uv run mypy --ignore-missing-imports artintel_bin/ bin/ tests/ yaml_shim.py
uv run pytest -v --tb=short tests/
```

**Zero errori richiesti prima di procedere in SOTA.**

## Principi di Verifica

1. **Evidence > Claims**: Ogni affermazione deve avere evidenza dal codice
2. **Trace Imports**: "Definito" ≠ "Utilizzato" — verifica gli import
3. **Runtime Truth**: .venv/site-packages è la fonte di verità per le API
4. **No Assumptions**: Se non puoi provarlo, non affermarlo

## Switch Modalità

Durante una sessione puoi cambiare modalità:
- "Passa a FAST" / "Switch to FAST" → Applica regole FAST
- "Passa a SOTA" / "Switch to SOTA" → Applica regole SOTA
- `/fast` o `/sota` → Stessi effetti

La modalità rimane attiva fino a cambio esplicito o fine sessione.
