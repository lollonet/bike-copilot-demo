# Commands (shared prompt library)

These files are **prompt commands** shared across tools:

- Claude Code: `~/.claude/commands/` → repo `commands/`
- Codex CLI: `~/.codex/prompts/` → repo `commands/`

## Conventions

- Keep commands tool-agnostic (they must work in Claude and Codex contexts).
- Follow `CORE.md` output sections for responses:
  - `Analisi:` `Piano:` `Patch:` `Test:` `Note:`
- Ask only blocking questions (max 3) and proceed with explicit assumptions when possible.

