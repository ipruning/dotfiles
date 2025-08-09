# echo ">>> .zshrc is loaded. Shell: $SHELL, Options: $-"

if [[ $OSTYPE == darwin* ]]; then
  if [ -d "/opt/homebrew/bin" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi

  local completion_paths=()

  [ -d "$HOME/dotfiles/config/shell/completions" ] && completion_paths+=("$HOME/dotfiles/config/shell/completions")

  completion_paths+=("${fpath[@]}")

  fpath=("${completion_paths[@]}")

  autoload -Uz compinit
  for dump in ~/.zcompdump(N.mh+24); do
    compinit
  done
  compinit -C

  # autoload -U +X bashcompinit && bashcompinit

  # if [ -d "$HOME/dotfiles/config/shell/completions" ]; then
  #   for completion in "$HOME/dotfiles/config/shell/completions"/*.bash; do
  #     [[ -f "$completion" ]] && source "$completion"
  #   done
  # fi

  if [ -d "$HOME/dotfiles" ]; then
    if [ -n "$ZSH_VERSION" ]; then
      local config_files=(
        "$HOME/dotfiles/config/shell/aliases.zsh"
        "$HOME/dotfiles/config/shell/env.zsh"
        "$HOME/dotfiles/config/shell/env.private.zsh"
      )

      for file in "${config_files[@]}"; do
        [[ -e "$file" ]] && source "$file"
      done
    fi
  fi
fi

if [[ $OSTYPE == linux* ]]; then
  local completion_paths=()

  [ -d "$HOME/dotfiles/config/shell/completions" ] && completion_paths+=("$HOME/dotfiles/config/shell/completions")

  completion_paths+=("${fpath[@]}")

  [ -d "/usr/share/zsh/site-functions" ] && completion_paths+=("/usr/share/zsh/site-functions")

  fpath=("${completion_paths[@]}")

  autoload -Uz compinit
  for dump in ~/.zcompdump(N.mh+24); do
    compinit
  done
  compinit -C

  if [ -d "$HOME/dotfiles" ]; then
    if [ -n "$ZSH_VERSION" ]; then
      local config_files=(
        "$HOME/dotfiles/config/shell/aliases.zsh"
        "$HOME/dotfiles/config/shell/env.zsh"
        "$HOME/dotfiles/config/shell/env.private.zsh"
      )

      for file in "${config_files[@]}"; do
        [[ -e "$file" ]] && source "$file"
      done
    fi
  fi

  source /opt/clash/script/common.sh && source /opt/clash/script/clashctl.sh && watch_proxy
fi
