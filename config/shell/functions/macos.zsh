function repo-fork-sync() {
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
}

function x86_64-zsh-login() {
  arch -x86_64 zsh --login
}

function x86_64-zsh-run() {
  arch -x86_64 zsh -c "$@"
}

function upgrade-all() {
  logger "Updating Homebrew..."
  if command -v brew &>/dev/null; then
    brew update
    brew upgrade
    logger "Pruning Homebrew..."
    brew cleanup
    brew autoremove
  fi

  logger "Updating mise..."
  if command -v mise &>/dev/null; then
    mise upgrade

    logger "Pruning mise..."
    mise prune
    mise reshim
  fi

  logger "Upgrading GitHub CLI extensions..."
  if command -v gh &>/dev/null; then
    gh extension upgrade --all
  fi

  logger "Updating tldr pages..."
  if command -v tldr &>/dev/null; then
    tldr --update
  fi

  logger "Backing up all packages..."
  local host=$(hostname -s)
  if command -v brew &>/dev/null; then
    brew bundle dump --file="$HOME/dotfiles/config/packages/brew_dump.${host}.txt" --force
    brew leaves >"$HOME/dotfiles/config/packages/brew_leaves.${host}.txt"
    brew list --installed-on-request >"$HOME/dotfiles/config/packages/brew_installed.${host}.txt"
  fi
  if command -v gh &>/dev/null; then
    gh extension list | awk '{print $3}' >"$HOME/dotfiles/config/packages/gh_extensions.${host}.txt"
  fi
  if [ -d "/Applications" ]; then
    find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME/dotfiles/config/packages/macos_applications.${host}.txt"
  fi
  if [ -d "/Applications/Setapp" ]; then
    find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME/dotfiles/config/packages/macos_setapp.${host}.txt"
  fi
}
