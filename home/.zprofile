# echo ">>> .zprofile is loaded. Shell: $SHELL, Options: $-"

if [[ $OSTYPE == darwin* ]]; then
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

  # if type nvim &> /dev/null; then
  #   alias vim="nvim"
  #   export EDITOR="nvim"
  #   export PSQL_EDITOR="nvim -c 'set filetype=sql'"
  #   export GIT_EDITOR="nvim"
  # else
  #   export EDITOR="vim"
  #   export PSQL_EDITOR="vim -c 'set filetype=sql'"
  #   export GIT_EDITOR="vim"
  # fi

  # if [[ -z "$ZELLIJ" ]]; then
  #   latest_session=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --reverse --short | grep -v "^repo-" | head -n 1)
  #   if [[ -n "$latest_session" ]]; then
  #     /opt/homebrew/bin/zellij attach --create "$latest_session"
  #   else
  #     /opt/homebrew/bin/zellij
  #   fi
  # fi

  # if [[ -n "$ZELLIJ" ]]; then
  # else
  #   local repo_path=$(pwd)
  #   if [[ "$repo_path" != "$HOME" ]] && git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [[ "$(git rev-parse --show-toplevel)" == "$repo_path" ]]; then
  #     local repo_name=$(basename "${repo_path}")
  #     zellij attach "repo-${repo_name}" 2>/dev/null || zellij --session "repo-${repo_name}"
  #   fi
  # fi

  if [[ "$TERM_PROGRAM" == "vscode" ]]; then
    export EDITOR="/opt/homebrew/bin/zed --wait"
    export VISUAL="/opt/homebrew/bin/zed --wait"
  fi

  if [[ "$TERM_PROGRAM" == "zed" ]]; then
    export EDITOR="/opt/homebrew/bin/zed --wait"
    export VISUAL="/opt/homebrew/bin/zed --wait"
  fi

  if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
    export EDITOR="/opt/homebrew/bin/zed --wait"
    export VISUAL="/opt/homebrew/bin/zed --wait"
    if [[ -z "$ZELLIJ" ]]; then
      latest_session=$(/opt/homebrew/bin/zellij list-sessions --no-formatting --short | grep -v "^repo-" | head -n 1)
      if [[ -n "$latest_session" ]]; then
        /opt/homebrew/bin/zellij attach --create "$latest_session"
      else
        /opt/homebrew/bin/zellij
      fi
    fi
  fi
fi

if [[ $OSTYPE == linux* ]]; then
  typeset -U path

  if [[ "$TERM_PROGRAM" == "vscode" ]]; then
    export EDITOR="/usr/local/bin/zed --wait"
    export VISUAL="/usr/local/bin/zed --wait"
  fi

  if [[ "$TERM_PROGRAM" == "zed" ]]; then
    export EDITOR="/usr/local/bin/zed --wait"
    export VISUAL="/usr/local/bin/zed --wait"
  fi

  if [[ "$TERM_PROGRAM" == "ghostty" ]]; then
    export EDITOR="/usr/local/bin/zed --wait"
    export VISUAL="/usr/local/bin/zed --wait"
  fi
fi
