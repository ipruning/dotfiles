#!/usr/bin/env bash

set -euo pipefail

SYSTEM_ARCH=$(uname -m)
SYSTEM_TYPE="unknown"

determine_system_type() {
  case "$OSTYPE" in
  darwin*)
    case $SYSTEM_ARCH in
    arm64*) SYSTEM_TYPE="mac_arm64" ;;
    x86_64*) SYSTEM_TYPE="mac_x86_64" ;;
    esac
    ;;
  linux*)
    case $SYSTEM_ARCH in
    arm64*) SYSTEM_TYPE="linux_arm64" ;;
    x86_64*) SYSTEM_TYPE="linux_x86_64" ;;
    *armv7l*) SYSTEM_TYPE="raspberry" ;;
    esac
    ;;
  esac
}

install_homebrew() {
  if ! command -v brew &>/dev/null; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  case $SYSTEM_TYPE in
  mac_x86_64)
    eval "$(/usr/local/homebrew/bin/brew shellenv)"
    ;;
  linux_x86_64)
    test -d ~/.linuxbrew && eval "$(~/.linuxbrew/bin/brew shellenv)"
    test -d /home/linuxbrew/.linuxbrew && eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
    test -r ~/.bash_profile && echo "eval \"\$($(brew --prefix)/bin/brew shellenv)\"" >>~/.bash_profile
    echo "eval \"\$($(brew --prefix)/bin/brew shellenv)\"" >>~/.profile
    ;;
  esac
}

setup_zsh() {
  case $SYSTEM_TYPE in
  mac_x86_64)
    chsh -s /bin/zsh
    ;;
  linux_x86_64)
    echo "Installing zsh"
    brew install zsh
    ZSH_PATH="$(brew --prefix)/bin/zsh"
    sudo sh -c "echo $ZSH_PATH >> /etc/shells"
    sudo chsh -s "$ZSH_PATH"
    ;;
  esac
}

install_oh_my_zsh() {
  echo "Installing oh-my-zsh"
  export CHSH=no RUNZSH=no KEEP_ZSHRC=yes
  sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc
}

setup_zsh_dotfiles() {
  echo "Installing zsh dotfiles"
  if ! grep -q "dotfiles/config/shell/zsh_bootstrap.sh" "$HOME/.zshrc"; then
    mv "$HOME/.zshrc" "$HOME/.zshrc.bak"
    cp "$HOME/dotfiles/config/shell/mac/zshrc.sh" "$HOME/.zshrc"
  fi

  if [ -e "$HOME/.zprofile" ]; then
    mv "$HOME/.zprofile" "$HOME/.zprofile.bak"
  fi
  cp "$HOME/dotfiles/config/shell/mac/zprofile.sh" "$HOME/.zprofile"
}

setup_dotfiles() {
  case $SYSTEM_TYPE in
  mac_x86_64)
    brew install golang
    ;;
  linux_x86_64)
    brew install mackup asdf

    echo "Installing mackup"
    ln -sf "$HOME/dotfiles/config/mackup/.mackup.cfg" "$HOME/.mackup.cfg"
    ln -sf "$HOME/dotfiles/config/mackup/.mackup" "$HOME/.mackup"

    echo "Restoring dotfiles"
    mackup restore ${MODE:+--force}

    sudo apt-get update
    sudo apt-get install -y coreutils curl

    echo "Installing asdf"
    asdf plugin add golang https://github.com/kennyp/asdf-golang.git
    asdf install golang 1.18.3
    asdf global golang 1.18.3

    echo "Reshiming asdf"
    asdf reshim
    ;;
  esac
}

main() {
  determine_system_type
  install_homebrew
  setup_zsh
  install_oh_my_zsh
  setup_zsh_dotfiles
  setup_dotfiles
}

main
