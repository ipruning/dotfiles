# echo ">>> .zshrc is loaded. Shell: $SHELL, Options: $-"

if [[ $OSTYPE = darwin* ]]; then
  if [ -d "/opt/homebrew/bin" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi

fpath=("$HOME/dotfiles/config/shell/completions" "${fpath[@]}")
autoload -Uz compinit
compinit -d ~/.zcompdump

if [[ $OSTYPE = darwin* ]]; then
  if [ -d "$HOME/dotfiles" ]; then
    if [ -n "$ZSH_VERSION" ]; then
      local config_files=(
        "$HOME/dotfiles/config/shell/env.zsh"
        "$HOME/dotfiles/config/shell/env.private.zsh"
        "$HOME/dotfiles/config/shell/aliases.zsh"
        "$HOME/dotfiles/config/shell/functions/misc.zsh"

        "$HOME/developer/localhost/prototypes/utils/zsh-functions/db.zsh"
        "$HOME/developer/localhost/prototypes/utils/zsh-functions/g.zsh"
      )

      for file in "${config_files[@]}"; do
        [[ -e "$file" ]] && source "$file"
      done
    fi
  fi
fi
