typeset -A g_commands=(
  aa "git add --all --verbose"
  ac "codegpt commit --no_confirm"
  ak "koji"
  b  "git browse"
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
    for key desc in ${(kv)g_commands}; do
      printf "  %-3s = %s\n" "$key" "$desc"
    done
    return
  fi

  local cmd=$1
  if (( ${+g_commands[$cmd]} )); then
    shift
    local command=(${=g_commands[$cmd]})
    "$command[@]" "$@"
    return
  fi

  git "$@"
}

compdef _g g

function _g() {
  if (( CURRENT == 2 )); then
    local -a subcommands
    for key desc in ${(kv)git_commands}; do
      subcommands+=("$key:${(q)desc}")
    done
    _describe -t commands "g subcommands" subcommands
  fi
}

function jump_to_repo() {
  local repo_path
  repo_path=$(tv git-repos)
  [[ -z "$repo_path" ]] && return
  if [[ -n "$ZELLIJ" ]]; then
    cd "${repo_path}"
  else
    cd "${repo_path}"
    local repo_name=$(basename "${repo_path}")
    zellij attach "${repo_name}" 2>/dev/null || zellij --session "${repo_name}"
  fi
}
