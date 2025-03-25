function repo-fork-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function x86_64-zsh-login() {
  arch -x86_64 zsh --login
}

function x86_64-zsh-run() {
  arch -x86_64 zsh -c "$@"
}

function jump-to-session() {
  if [[ -n "$ZELLIJ" ]]; then
  else
    if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
      zj_sessions=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --short)
      case $(echo "$zj_sessions" | grep -c '^.') in
      0)
        /opt/homebrew/bin/zellij
        ;;
      *)
        selected_session=$(echo "$zj_sessions" | /opt/homebrew/bin/tv --no-preview) &&
          [[ -n "$selected_session" ]] && /opt/homebrew/bin/zellij attach "$selected_session"
        ;;
      esac
    fi
  fi
}

function jump-to-repo() {
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
