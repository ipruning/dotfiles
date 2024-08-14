#!/usr/bin/env bash

set -euo pipefail

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly NORMAL='\033[0m'

print_message() {
  local color=$1
  local message=$2
  echo -e "${color}${message}${NORMAL}"
}

detect_system() {
  SYSTEM_ARCH=$(uname -m)
  case "$OSTYPE" in
  darwin*)
    case $SYSTEM_ARCH in
    arm64*) SYSTEM_TYPE="mac_arm64" ;;
    x86_64*) SYSTEM_TYPE="mac_x86_64" ;;
    *) SYSTEM_TYPE="unknown" ;;
    esac
    ;;
  linux*)
    case $SYSTEM_ARCH in
    x86_64*) SYSTEM_TYPE="linux_x86_64" ;;
    *armv7l*) SYSTEM_TYPE="raspberry" ;;
    *) SYSTEM_TYPE="unknown" ;;
    esac
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac

  export SYSTEM_TYPE
}

clone_dotfiles() {
  print_message "$BLUE" "Cloning dotfiles repository..."
  if [ -d "$HOME/dotfiles" ]; then
    print_message "$YELLOW" "Dotfiles directory already exists. Removing..."
    rm -rf "$HOME/dotfiles"
  fi
  git clone --depth 1 https://github.com/ipruning/dotfiles.git "$HOME/dotfiles"
}

install_homebrew() {
  if ! command -v brew &>/dev/null; then
    print_message "$BLUE" "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  else
    print_message "$GREEN" "Homebrew is already installed."
  fi

  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    eval "$(/opt/homebrew/bin/brew shellenv)"
    ;;
  linux_x86_64)
    if [[ -d /home/linuxbrew/.linuxbrew ]]; then
      eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
    elif [[ -d ~/.linuxbrew ]]; then
      eval "$(~/.linuxbrew/bin/brew shellenv)"
    fi

    if ! grep -q "eval \"\$($(brew --prefix)/bin/brew shellenv)\"" ~/.profile; then
      echo "eval \"\$($(brew --prefix)/bin/brew shellenv)\"" >>~/.profile
    fi
    ;;
  esac
}

setup_zsh() {
  print_message "$BLUE" "Setting up Zsh..."
  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    if [[ $SHELL != "/bin/zsh" ]]; then
      print_message "$YELLOW" "Changing default shell to Zsh..."
      chsh -s /bin/zsh || print_message "$RED" "Failed to change shell. Please change it manually."
    else
      print_message "$GREEN" "Zsh is already the default shell."
    fi
    ;;
  linux_x86_64)
    if ! command -v zsh &>/dev/null; then
      brew install zsh
      ZSH_PATH="$(brew --prefix)/bin/zsh"
      if ! grep -q "$ZSH_PATH" /etc/shells; then
        echo "$ZSH_PATH" | sudo tee -a /etc/shells
      fi
      print_message "$YELLOW" "Changing default shell to Zsh..."
      chsh -s "$ZSH_PATH" || print_message "$RED" "Failed to change shell. Please change it manually."
    else
      print_message "$GREEN" "Zsh is already installed."
    fi
    ;;
  esac
}

install_oh_my_zsh() {
  print_message "$BLUE" "Installing Oh My Zsh..."
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    export CHSH=no RUNZSH=no KEEP_ZSHRC=yes
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc
  else
    print_message "$GREEN" "Oh My Zsh is already installed."
  fi
}

setup_dotfiles() {
  print_message "$BLUE" "Setting up dotfiles..."
  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    brew install golang
    ;;
  linux_x86_64)
    brew install mackup asdf

    print_message "$BLUE" "Installing mackup"
    ln -sf "$HOME/dotfiles/config/mackup/.mackup.cfg" "$HOME/.mackup.cfg"
    ln -sf "$HOME/dotfiles/config/mackup/.mackup" "$HOME/.mackup"

    print_message "$BLUE" "Restoring dotfiles"
    mackup restore --force

    sudo apt-get update
    sudo apt-get install -y coreutils curl

    print_message "$BLUE" "Installing asdf"
    asdf plugin add golang https://github.com/kennyp/asdf-golang.git
    asdf install golang 1.22.3
    asdf global golang 1.22.3

    print_message "$BLUE" "Reshiming asdf"
    asdf reshim
    ;;
  esac
}

main() {
  detect_system
  clone_dotfiles
  install_homebrew
  setup_zsh
  install_oh_my_zsh
  setup_dotfiles
  print_message "$GREEN" "Bootstrap process completed successfully!"
}

main
