# echo ">>> .zshrc is loaded. Shell: $SHELL, Options: $-"

if [[ $OSTYPE = darwin* ]]; then
  if [ -d "/opt/homebrew/bin" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi

  if [ -d "$HOME/dotfiles/config/shell/completions" ]; then
    fpath=("$HOME/dotfiles/config/shell/completions" "${fpath[@]}")
  fi

  autoload -Uz compinit
  compinit -d ~/.zcompdump

  autoload -U +X bashcompinit && bashcompinit

  if [ -d "$HOME/dotfiles/config/shell/completions" ]; then
    for completion in "$HOME/dotfiles/config/shell/completions"/*.bash; do
      [[ -f "$completion" ]] && source "$completion"
    done
  fi

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
