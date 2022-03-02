#!/bin/bash

RED="$(tput setaf 1)"
GREEN="$(tput setaf 2)"
YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

# main
function main {
  # init dotfiles
  git clone --depth 1 https://github.com/Spehhhhh/dotfiles.git "$HOME"/dotfiles

  # init
  case "$OSTYPE" in
    darwin*)  sh "$HOME"/dotfiles/bootstrap_macos.sh ;;
    linux*)   echo "TODO" ;;
    msys*)    echo "TODO" ;;
    *)        echo "unknown: $OSTYPE" ;;
  esac
}

# Checking the environment
if [ -d "$HOME"/dotfiles ]; then
	echo "${YELLOW}You already have dotfiles installed."
	echo "${GREEN}Please remove $HOME/dotfiles if you want to re-install."
	exit
fi

echo "${RED}This will overwrite existing files in your home directory. Are you sure? (y/n) "
read -r

if [[ $REPLY =~ ^[Yy] ]]; then
	echo "${BLUE}Cloning dotfiles...${NORMAL}"
	main
else
	echo "";
fi;
