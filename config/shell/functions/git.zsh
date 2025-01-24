typeset -A git_commands
git_commands=(
  a 'git add --all'
  c 'git commit -m'
  d 'git diff'
  l 'git lg'
  s 'git status'
)

g() {
  if [[ $# -eq 0 ]]; then
    git status
  else
    local cmd=$1
    if (( ${+git_commands[$cmd]} )); then
      if [[ $cmd == "c" ]]; then
        shift
        git commit -m "$*"
      else
        eval ${git_commands[$cmd]}
      fi
    else
      git "$@"
    fi
  fi
}

compdef _g g

function _g() {
  local -a subcommands
  for key desc in ${(kv)git_commands}; do
    subcommands+=("$key:${desc#git }")
  done

  if (( CURRENT == 2 )); then
    _describe -t commands 'g subcommands' subcommands
    _git
  else
    shift words
    (( CURRENT -- ))
    _git
  fi
}
