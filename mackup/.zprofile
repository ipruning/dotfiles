# echo ">>> .zprofile is loaded. Shell: $SHELL, Options: $-"

if [[ $OSTYPE = darwin* ]]; then
  # >>> conda initialize >>>
  # !! Contents within this block are managed by 'conda init' !!
  __conda_setup="$('/opt/homebrew/Caskroom/miniforge/base/bin/conda' 'shell.bash' 'hook' 2>/dev/null)"
  if [ $? -eq 0 ]; then
    eval "$__conda_setup"
  else
    if [ -f "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh" ]; then
      . "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh"
    else
      export PATH="/opt/homebrew/Caskroom/miniforge/base/bin:$PATH"
    fi
  fi
  unset __conda_setup
  # <<< conda initialize <<<

  if [[ "$TERM_PROGRAM" == "zed" ]]; then
    if [[ -n "$ZELLIJ" ]]; then
    else
      local repo_path=$(pwd)
      if [[ "$repo_path" != "$HOME" ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [[ "$(git rev-parse --show-toplevel)" == "$repo_path" ]]; then
        local repo_name=$(basename "${repo_path}")
        zellij attach "${repo_name}" 2>/dev/null || zellij --session "${repo_name}"
      fi
    fi
  fi

  function jump_to_session() {
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
fi
