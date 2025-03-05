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
  brew update
  brew upgrade

  logger "Pruning Homebrew..."
  brew cleanup
  brew autoremove

  logger "Updating mise..."
  mise upgrade

  logger "Pruning mise..."
  mise prune
  mise reshim

  logger "Upgrading GitHub CLI extensions..."
  gh extension upgrade --all

  logger "Updating tldr pages..."
  tldr --update

  logger "Backing up all packages..."
  local host=$(hostname -s)
  brew bundle dump --file="$HOME/dotfiles/config/packages/brew_dump.${host}.txt" --force
  brew leaves >"$HOME/dotfiles/config/packages/brew_leaves.${host}.txt"
  brew list --installed-on-request >"$HOME/dotfiles/config/packages/brew_installed.${host}.txt"
  gh extension list | awk '{print $3}' >"$HOME/dotfiles/config/packages/gh_extensions.${host}.txt"
  find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME/dotfiles/config/packages/macos_applications.${host}.txt"
  find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME/dotfiles/config/packages/macos_setapp.${host}.txt"
}
