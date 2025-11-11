#!/usr/bin/env bash
# Bash completion for adopt_standards.sh

_adopt_standards_complete() {
  local cur prev opts
  COMPREPLY=()
  cur=${COMP_WORDS[COMP_CWORD]}
  prev=${COMP_WORDS[COMP_CWORD-1]}

  opts="--source-dir --source-url --ref --uv --paths --hooks --ci --req-id --branch --no-branch --dry-run -h --help"

  case "$prev" in
    --uv)
      COMPREPLY=( $(compgen -W "adopt skip" -- "$cur") ); return 0 ;;
    --hooks)
      COMPREPLY=( $(compgen -W "enable skip" -- "$cur") ); return 0 ;;
    --ci)
      COMPREPLY=( $(compgen -W "adopt skip" -- "$cur") ); return 0 ;;
    --source-dir)
      COMPREPLY=( $(compgen -d -- "$cur") ); return 0 ;;
    --paths)
      COMPREPLY=( $(compgen -d -- "$cur") ); return 0 ;;
  esac

  if [[ "$cur" == -* ]]; then
    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
    return 0
  fi
}

# Register for both path and bare name
complete -F _adopt_standards_complete adopt_standards.sh 2>/dev/null || true
complete -F _adopt_standards_complete scripts/adopt_standards.sh 2>/dev/null || true

