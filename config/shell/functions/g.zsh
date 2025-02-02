typeset -A git_commands=(
  aa "git add --all --verbose"
  ac "codegpt commit --no_confirm"
  c  "git commit"
  d  "git diff"
  j  "jump_to_repo"
  l  "git lg"
  s  "git status"
)

function g() {
  if [[ ! -d .git ]] && [[ $1 != "help" ]] && [[ $1 != "j" ]]; then
    return 1
  fi

  if [[ $# -eq 0 ]]; then
    command -v lazygit >/dev/null 2>&1 && lazygit || git status
    return
  fi

  if [[ $1 == "help" ]]; then
    echo "Usage: g [subcommand]"
    for key desc in ${(kv)git_commands}; do
      printf "  %-3s = %s\n" "$key" "$desc"
    done
    return
  fi

  local cmd=$1
  if (( ${+git_commands[$cmd]} )); then
    shift

    if [[ $cmd == "j" ]]; then
      local command=(${=git_commands[$cmd]})
      "$command[@]" "$@"
      return
    fi
 
    local command=(${=git_commands[$cmd]})
    "$command[@]" "$@"
    return
  fi

  git "$@"
}

compdef _g g

function _g() {
  local -a subcommands

  for key desc in ${(kv)git_commands}; do
    subcommands+=("$key:${(q)desc}")
  done

  if (( CURRENT == 2 )); then
    _describe -t commands "g subcommands" subcommands
    return
  else
    shift words
    (( CURRENT-- ))
    _git
  fi
}
