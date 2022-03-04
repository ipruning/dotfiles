#!/usr/bin/env bash

RED="$(tput setaf 1)"
GREEN="$(tput setaf 2)"
YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

# main
function main {
  echo "${BLUE}Cloning dotfiles...${NORMAL}"
  git clone --depth 1 https://github.com/Spehhhhh/dotfiles.git "$HOME"/dotfiles

  # init
  echo "${BLUE}Runing the bootstrap script...${NORMAL}"
  case "$OSTYPE" in
  darwin*)
    sh "$HOME"/dotfiles/scripts/bootstrap_mac.sh
    ;;
  linux*)
    if [[ "$(uname -m)" == *armv7l* ]]; then
      sh "$HOME"/dotfiles/scripts/bootstrap_raspberry.sh
    else
      echo "${RED}Unsupported system architecture.${NORMAL}"
    fi
    ;;
  msys*)
    echo "${RED}Unsupported system architecture.${NORMAL}"
    ;;
  *)
    echo "${RED}unknown: $OSTYPE${NORMAL}"
    ;;
  esac
}

# Checking the environment
if [ -d "$HOME"/dotfiles ]; then
  echo "${YELLOW}You already have dotfiles installed.${NORMAL}"
  echo "${GREEN}Please remove $HOME/dotfiles if you want to re-install.${NORMAL}"
  exit
fi

echo "${RED}This will overwrite existing files in your home directory. Are you sure? (y/n)${NORMAL}"
read -r

if [[ $REPLY =~ ^[Yy] ]]; then
  main
else
  echo ""
fi
