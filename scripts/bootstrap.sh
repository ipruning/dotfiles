#!/usr/bin/env bash

# TODO Remove ASDF

set -euo pipefail

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;34m'
readonly NORMAL='\033[0m'

DOTFILES_DIR="$HOME/dotfiles"
MODE=""

print_message() {
  local color=$1
  local message=$2
  printf "${color}%s${NORMAL}\n" "$message"
}

detect_system() {
  local system_arch
  system_arch=$(uname -m)
  case "$OSTYPE" in
  darwin*)
    case $system_arch in
    arm64*) SYSTEM_TYPE="mac_arm64" ;;
    x86_64*) SYSTEM_TYPE="mac_x86_64" ;;
    *) SYSTEM_TYPE="unknown" ;;
    esac
    ;;
  linux*)
    case $system_arch in
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

setup_homebrew() {
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

setup_oh_my_zsh() {
  print_message "$BLUE" "Installing Oh My Zsh..."
  if [[ ! -d "$HOME/.oh-my-zsh" ]]; then
    export CHSH=no RUNZSH=no KEEP_ZSHRC=yes
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" --unattended --keep-zshrc
  else
    print_message "$GREEN" "Oh My Zsh is already installed."
  fi
}

setup_omz_plugins() {
  print_message "$BLUE" "Installing zsh plugins..."
  ZSH_CUSTOM=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}

  local plugins=(
    "https://github.com/paulirish/git-open.git"
    "https://github.com/zsh-users/zsh-autosuggestions"
    "https://github.com/zsh-users/zsh-syntax-highlighting.git"
  )

  for plugin in "${plugins[@]}"; do
    local plugin_name
    plugin_name=$(basename "$plugin" .git)
    if [[ ! -d "$ZSH_CUSTOM/plugins/$plugin_name" ]]; then
      git clone "$plugin" "$ZSH_CUSTOM/plugins/$plugin_name"
    else
      print_message "$GREEN" "Plugin $plugin_name is already installed."
    fi
  done
}

setup_dotfiles() {
  print_message "$BLUE" "Setting up dotfiles..."
  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    # TODO: Implement macOS-specific setup
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

setup_packages() {
  print_message "$BLUE" "Installing brew packages..."
  case $SYSTEM_TYPE in
  mac_x86_64 | mac_arm64)
    brew bundle --file="$HOME/dotfiles/assets/others/packages/Brewfile_dev"
    ;;
  linux_x86_64)
    # TODO: Implement Linux-specific package installation
    ;;
  esac

  print_message "$BLUE" "Installing cargo packages..."
  xargs <"$HOME/dotfiles/assets/others/packages/cargo.txt" -n 1 cargo install

  print_message "$BLUE" "Installing npm packages..."
  xargs npm install --location=global <"$HOME/dotfiles/assets/others/packages/npm.txt"

  print_message "$BLUE" "Installing pipx packages..."
  xargs <"$HOME/dotfiles/assets/others/packages/pipx.txt" -n 1 pipx install
}

usage() {
  echo "Usage: $(basename "$0") [-f] [-h]"
  echo "  -f  Force mode: Remove existing dotfiles and reinstall"
  echo "  -h  Display this help message"
}

main() {
  detect_system
  setup_homebrew
  setup_zsh
  setup_oh_my_zsh
  setup_omz_plugins
  setup_dotfiles
  setup_packages
  print_message "$GREEN" "Bootstrap process completed successfully!"
}

while getopts ":fh" opt; do
  case $opt in
  f)
    MODE="force"
    ;;
  h)
    usage
    exit 0
    ;;
  \?)
    echo "Invalid option: -$OPTARG" >&2
    usage
    exit 1
    ;;
  esac
done

shift $((OPTIND - 1))

if [[ $# -gt 0 ]]; then
  echo "Unexpected arguments: $*" >&2
  usage
  exit 1
fi

if [[ $MODE == "force" ]]; then
  rm -rf "$DOTFILES_DIR"
  main
else
  print_message "$RED" "This will overwrite existing files in your home directory. Are you sure? (y/n)"
  read -r response
  if [[ $response =~ ^[Yy] ]]; then
    if [[ -d "$DOTFILES_DIR" ]]; then
      print_message "$YELLOW" "You already have dotfiles installed."
      print_message "$GREEN" "Please remove $DOTFILES_DIR if you want to re-install."
      exit 1
    else
      setup_dotfiles
      main
    fi
  else
    print_message "$YELLOW" "Aborting..."
  fi
fi

print_message "$GREEN" "Done"
print_message "$GREEN" "You can install the VS Code plugin by running the following command."
print_message "$GREEN" "xargs < $HOME/dotfiles/assets/others/packages/vscode_extensions.txt -n 1 code --install-extension"
