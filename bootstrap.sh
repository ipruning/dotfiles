#!/usr/bin/env bash

set -euo pipefail

# Define color variables
readonly RED=$(tput setaf 1)
readonly GREEN=$(tput setaf 2)
readonly YELLOW=$(tput setaf 3)
readonly BLUE=$(tput setaf 4)
readonly NORMAL=$(tput sgr0)

DOTFILES_DIR="$HOME/dotfiles"
MODE=""

setup_dotfiles() {
  echo "${BLUE}Cloning dotfiles...${NORMAL}"
  git clone --depth 1 https://github.com/ipruning/dotfiles.git "$DOTFILES_DIR"
}

bootstrap() {
  echo "${BLUE}Setting up dotfiles...${NORMAL}"
  # shellcheck source=/dev/null
  source "$DOTFILES_DIR/bin/csys" # check SYSTEM_OS, SYSTEM_ARCH
  case "$OSTYPE" in
  darwin*)
    # shellcheck source=/dev/null
    source "$DOTFILES_DIR/scripts/bootstrap_mac.sh"
    ;;
  linux*)
    case "$(uname -m)" in
    armv7l* | x86_64*)
      echo "${RED}Unsupported system architecture.${NORMAL}"
      ;;
    *)
      echo "${RED}Unsupported system architecture.${NORMAL}"
      ;;
    esac
    ;;
  msys*)
    echo "${RED}Unsupported system architecture.${NORMAL}"
    ;;
  *)
    echo "${RED}Unknown OS type: $OSTYPE${NORMAL}"
    ;;
  esac
}

usage() {
  echo "Usage: $(basename "$0") [-f] [-h]"
  echo "  -f  Force mode: Remove existing dotfiles and reinstall"
  echo "  -h  Display this help message"
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
  bootstrap
else
  echo "${RED}This will overwrite existing files in your home directory. Are you sure? (y/n)${NORMAL}"
  read -r response
  if [[ $response =~ ^[Yy] ]]; then
    if [[ -d "$DOTFILES_DIR" ]]; then
      echo "${YELLOW}You already have dotfiles installed.${NORMAL}"
      echo "${GREEN}Please remove $DOTFILES_DIR if you want to re-install.${NORMAL}"
      exit 1
    else
      setup_dotfiles
      bootstrap
    fi
  else
    echo "${YELLOW}Aborting...${NORMAL}"
  fi
fi
