# /sync — Git Branch Sync (safe, repo-agnostic)

## Intent

Synchronize your local branch with the default branch on `origin` (and optionally rebase).

$ARGUMENTS

## Rules

- Never force-push without explicit confirmation.
- Don’t lose uncommitted work: stash or commit intentionally.
- Prefer detecting the default branch instead of assuming `main`/`develop`.

## Suggested flow

1. **Pre-flight**
   - `git status -sb`
   - Detect default branch:
     - `git symbolic-ref --quiet refs/remotes/origin/HEAD` (fallback: `origin/main`)
   - `git fetch --all --prune`

2. **Sync**
   - If current branch is feature/topic:
     - Rebase onto default branch (preferred) or merge if user requests.
   - If current branch *is* the default branch:
     - Fast-forward it to `origin/<default>`.

3. **Verify**
   - `git status -sb`
   - Show the resulting SHAs (`git log -1 --oneline`).

## Output

Use `CORE.md` standard sections:
Analisi:
Piano:
Patch:
Test:
Note:

