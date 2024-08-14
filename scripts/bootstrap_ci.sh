#!/usr/bin/env bash

set -euo pipefail

readonly RED=$(tput setaf 1)
readonly GREEN=$(tput setaf 2)
readonly YELLOW=$(tput setaf 3)
readonly BLUE=$(tput setaf 4)
readonly NORMAL=$(tput sgr0)

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

install_homebrew() {
  if ! command -v brew &>/dev/null; then
    echo "${BLUE}Installing Homebrew...${NORMAL}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  else
    echo "${GREEN}Homebrew is already installed.${NORMAL}"
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
  echo "${BLUE}Setting up Zsh...${NORMAL}"
  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    if [[ $SHELL != "/bin/zsh" ]]; then
      chsh -s /bin/zsh
    else
      echo "${GREEN}Zsh is already the default shell.${NORMAL}"
    fi
    ;;
  linux_x86_64)
    if ! command -v zsh &>/dev/null; then
      brew install zsh
      ZSH_PATH="$(brew --prefix)/bin/zsh"
      if ! grep -q "$ZSH_PATH" /etc/shells; then
        echo "$ZSH_PATH" | sudo tee -a /etc/shells
      fi
      sudo chsh -s "$ZSH_PATH" "$USER"
    else
      echo "${GREEN}Zsh is already installed.${NORMAL}"
    fi
    ;;
  esac
}

install_oh_my_zsh() {
  echo "${BLUE}Installing Oh My Zsh...${NORMAL}"
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    export CHSH=no RUNZSH=no KEEP_ZSHRC=yes
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc
  else
    echo "${GREEN}Oh My Zsh is already installed.${NORMAL}"
  fi
}

setup_dotfiles() {
  echo "${BLUE}Setting up dotfiles...${NORMAL}"
  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    brew install golang
    ;;
  linux_x86_64)
    brew install mackup asdf

    echo "${BLUE}Installing mackup${NORMAL}"
    ln -sf "$HOME/dotfiles/config/mackup/.mackup.cfg" "$HOME/.mackup.cfg"
    ln -sf "$HOME/dotfiles/config/mackup/.mackup" "$HOME/.mackup"

    echo "${BLUE}Restoring dotfiles${NORMAL}"
    mackup restore --force

    sudo apt-get update
    sudo apt-get install -y coreutils curl

    echo "${BLUE}Installing asdf${NORMAL}"
    asdf plugin add golang https://github.com/kennyp/asdf-golang.git
    asdf install golang 1.22.3
    asdf global golang 1.22.3

    echo "${BLUE}Reshiming asdf${NORMAL}"
    asdf reshim
    ;;
  esac
}

main() {
  detect_system
  install_homebrew
  setup_zsh
  install_oh_my_zsh
  setup_dotfiles
  echo "${GREEN}Bootstrap process completed successfully!${NORMAL}"
}

main
