# zmodload zsh/zprof

if [ -d "$HOME/dotfiles" ]; then
  if [ -n "$ZSH_VERSION" ]; then
    local config_files=(
      "$HOME/dotfiles/config/shell/env.zsh"
      "$HOME/dotfiles/config/shell/env_private.zsh"
      "$HOME/dotfiles/config/shell/aliases.zsh"
      "$HOME/dotfiles/config/shell/functions/ai.zsh"
      "$HOME/dotfiles/config/shell/functions/db.zsh"
      "$HOME/dotfiles/config/shell/functions/misc.zsh"
    )

    for file in "${config_files[@]}"; do
      [[ -f "$file" ]] && source "$file"
    done
  fi
fi

# zprof
