#!/usr/bin/env bash
# Bash completion for status.sh

_status_complete() {
  local cur
  COMPREPLY=()
  cur=${COMP_WORDS[COMP_CWORD]}
  if [[ "$cur" == -* ]]; then
    COMPREPLY=( $(compgen -W "--fix" -- "$cur") )
  fi
}

complete -F _status_complete status.sh 2>/dev/null || true
complete -F _status_complete scripts/status.sh 2>/dev/null || true

