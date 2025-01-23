if [[ $OSTYPE = darwin* ]]; then
  if [ -d "$HOME/dotfiles" ]; then
    if [ -n "$ZSH_VERSION" ]; then
      local config_files=(
        "$HOME/dotfiles/config/shell/env.bash"
        "$HOME/dotfiles/config/shell/env_private.bash"
        "$HOME/dotfiles/config/shell/aliases.bash"
        "$HOME/dotfiles/config/shell/functions/ai.bash"
        "$HOME/dotfiles/config/shell/functions/db.bash"
        "$HOME/dotfiles/config/shell/functions/misc.bash"
      )

      for file in "${config_files[@]}"; do
        [[ -e "$file" ]] && source "$file"
      done
    fi
  fi
fi

# sproxy
