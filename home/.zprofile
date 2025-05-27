# echo ">>> .zprofile is loaded. Shell: $SHELL, Options: $-"

if [[ $OSTYPE = darwin* ]]; then
  typeset -U path

  # >>> conda initialize >>>
  # !! Contents within this block are managed by 'conda init' !!
  # __conda_setup="$('/opt/homebrew/Caskroom/miniforge/base/bin/conda' 'shell.bash' 'hook' 2>/dev/null)"
  # if [ $? -eq 0 ]; then
  #   eval "$__conda_setup"
  # else
  #   if [ -f "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh" ]; then
  #     . "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh"
  #   else
  #     export PATH="/opt/homebrew/Caskroom/miniforge/base/bin:$PATH"
  #   fi
  # fi
  # unset __conda_setup
  # <<< conda initialize <<<

  if [[ "$TERM_PROGRAM" == "vscode" ]]; then
    export EDITOR="zed --wait"
    export VISUAL="zed --wait"
  fi

  if [[ "$TERM_PROGRAM" == "zed" ]]; then
    export EDITOR="zed --wait"
    export VISUAL="zed --wait"
    # if [[ -n "$ZELLIJ" ]]; then
    # else
    #   local repo_path=$(pwd)
    #   if [[ "$repo_path" != "$HOME" ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [[ "$(git rev-parse --show-toplevel)" == "$repo_path" ]]; then
    #     local repo_name=$(basename "${repo_path}")
    #     zellij attach "repo-${repo_name}" 2>/dev/null || zellij --session "repo-${repo_name}"
    #   fi
    # fi
  fi

  if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
    export EDITOR="zed --wait"
    export VISUAL="zed --wait"
    if [[ -z "$ZELLIJ" ]]; then
      latest_session=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --reverse --short | grep -v "^repo-" | head -n 1)
      if [[ -n "$latest_session" ]]; then
        /opt/homebrew/bin/zellij attach --create "$latest_session"
      else
        /opt/homebrew/bin/zellij
      fi
    fi
  fi

fi
