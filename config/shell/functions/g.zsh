typeset -A git_commands=(
  a  'git add'
  aa 'git add --all'
  ac 'codegpt commit --no_confirm'
  c  'git commit -m'
  cc 'koji'
  d  'git diff'
  j  'jump_to_repo'
  l  'git lg'
  s  'git status'
)

g() {
  # Early return if not in a git repo (except for 'help' and 'j' commands)
  if [[ ! -d .git ]] && [[ $1 != "help" ]] && [[ $1 != "j" ]]; then
    return 1
  fi

  # No arguments: show status or lazygit
  if [[ $# -eq 0 ]]; then
    command -v lazygit >/dev/null 2>&1 && lazygit || git status
    return
  fi

  # Help command
  if [[ $1 == "help" ]]; then
    echo "Usage: g [subcommand]"
    for key desc in ${(kv)git_commands}; do
      printf "  %-3s = %s\n" "$key" "$desc"
    done
    return
  fi

  # Handle known subcommands
  local cmd=$1
  if (( ${+git_commands[$cmd]} )); then
    shift
    # Special handling for jump command
    if [[ $cmd == "j" ]]; then
      local command=(${=git_commands[$cmd]})
      "$command[@]" "$@"
      return
    fi
    
    # Special handling for commit command
    if [[ $cmd == "c" ]]; then
      git commit -m "$*"
      return
    fi
    
    # Execute other known commands
    local command=(${=git_commands[$cmd]})
    "$command[@]" "$@"
    return
  fi

  # Fall back to regular git command
  git "$@"
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
