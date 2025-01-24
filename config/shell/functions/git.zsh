typeset -A git_commands=(
  a  'git add --all'
  ac 'op run -- codegpt commit --no_confirm'
  c  'git commit -m'
  d  'git diff'
  lg 'git lg'
  s  'git status'
)

g() {
  if [[ $# -eq 0 ]]; then
    git status
  elif [[ $1 == "help" ]]; then
    echo "Usage: g [subcommand]"
    for key desc in ${(kv)git_commands}; do
      printf "  %-3s = %s\n" "$key" "$desc"
    done
    return
  else
    local cmd=$1
    if (( ${+git_commands[$cmd]} )); then
      shift
      if [[ $cmd == "c" ]]; then
        git commit -m "$@"
      else
        local command=(${=git_commands[$cmd]})
        "$command[@]" "$@"
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
    subcommands+=("$key:${(q)desc}")
  done

  if (( CURRENT == 2 )); then
    _describe -t commands 'g subcommands' subcommands
    return
  else
    shift words
    (( CURRENT-- ))
    _git
  fi
}
