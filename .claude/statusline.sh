#!/bin/bash

# Read JSON input from stdin; fail soft if jq missing or input empty.
if ! command -v jq >/dev/null 2>&1; then
  echo "[statusline] jq not installed" >&2
  exit 0
fi

input=$(cat)

# Extract current directory with fallback to "." if missing/null.
current_dir=$(echo "$input" | jq -er '.workspace.current_dir // "."' 2>/dev/null) || current_dir="."

# Get username and hostname (mimicking shell PS1)
user=$(whoami)
host=$(hostname -s)

# Format: user@hostname:directory (dimmed)
printf "\033[2m%s@%s:%s\033[0m" "$user" "$host" "$current_dir"
