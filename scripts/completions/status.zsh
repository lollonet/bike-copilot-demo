#compdef status.sh scripts/status.sh

_status() {
  _arguments \
    '--fix[Apply ruff fixes and format]' \
    '*:file:_files'
}

_status "$@"

