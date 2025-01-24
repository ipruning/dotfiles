function zj() {
  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed. please install it first."
    return 1
  fi

  if [[ "$ZELLIJ" == "0" ]]; then
    echo "Already in a zellij session. please exit first."
    return 1
  fi

  # get existing sessions
  local sessions=$(zellij list-sessions --no-formatting)

  # Different behavior based on number of existing sessions
  if [[ -n "$sessions" ]]; then
    # Count total number of sessions (including EXITED ones)
    local session_count=$(echo "$sessions" | grep -c "^")

    if [[ "$session_count" -eq 1 ]]; then
      # If only one session exists, attach directly
      local session=$(echo "$sessions" | awk '{print $1}')
      zellij attach "${session}"
    else
      # Multiple sessions - show selection with all sessions
      local session=$(echo "$sessions" | awk '{
        session_name=$1; $1="";
        if ($0 ~ /EXITED/) print "\033[31m" session_name "\033[0m\t" $0;
        else print "\033[32m" session_name "\033[0m\t" $0;
      }' | column -t -s $'\t' | fzf --ansi --exit-0 --header="Select a session to attach (or press Esc to create new):" | awk '{print $1}')

      if [[ -n "$session" ]]; then
        zellij attach "${session}"
      else
        zellij
      fi
    fi
  else
    # No existing sessions - Esc creates new
    local session=$(echo "" | fzf --ansi --print-query --header="Enter new session name (or press Esc for unnamed session):" | head -1)

    if [[ -n "$session" ]]; then
      zellij --session "$session"
    else
      zellij
    fi
  fi
}

function repo-fork-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function ssh-auth-sock-set() {
  export SSH_AUTH_SOCK="$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"
  ssh-add -L
}

function ssh-auth-sock-unset() {
  unset SSH_AUTH_SOCK
}

function proxy-set() {
  export https_proxy=http://127.0.0.1:6152
  export http_proxy=http://127.0.0.1:6152
  export all_proxy=socks5://127.0.0.1:6153
}

function proxy-unset() {
  unset https_proxy http_proxy all_proxy
}
