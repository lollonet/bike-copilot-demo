#compdef adopt_standards.sh scripts/adopt_standards.sh

_adopt_standards() {
  _arguments \
    '(-h --help)'{-h,--help}'[show help]' \
    '--source-dir[Source template directory]:directory:_files -/' \
    '--source-url[Template git URL]:url:_message -r url' \
    '--ref[Git ref (tag/branch)]:ref:(main HEAD v0.1.1)' \
    '--uv[Adopt uv project scaffolding]:mode:(adopt skip)' \
    '--paths[Space-separated code paths]:paths:_files -/' \
    '--hooks[Enable .githooks]:mode:(enable skip)' \
    '--ci[Adopt CI workflow]:mode:(adopt skip)' \
    '--req-id[Tracking requirement id]:id:_message -r id' \
    '--branch[Branch to create/switch]:name:_message -r name' \
    '--no-branch[Apply on current branch]' \
    '--dry-run[Print actions without writing]' \
    '*:file:_files'
}

_adopt_standards "$@"

