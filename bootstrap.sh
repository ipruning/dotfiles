#!/usr/bin/env bash

RED="$(tput setaf 1)"
GREEN="$(tput setaf 2)"
YELLOW="$(tput setaf 3)"
BLUE="$(tput setaf 4)"
NORMAL="$(tput sgr0)"

function setup_dotfiles {
  echo "${BLUE}Cloning dotfiles...${NORMAL}"
  git clone --depth 1 https://github.com/ipruning/dotfiles.git "$HOME"/dotfiles
}

function bootstrap {
  echo "${BLUE}Setting up dotfiles...${NORMAL}"
  source "$HOME"/dotfiles/bin/csys # check SYSTEM_OS, SYSTEM_ARCH
  case "$OSTYPE" in
  darwin*)
    source "$HOME"/dotfiles/scripts/bootstrap_mac.sh
    ;;
  linux*)
    if [[ "$(uname -m)" == *armv7l* ]]; then
      echo "${RED}Unsupported system architecture.${NORMAL}"
    elif [[ "$(uname -m)" == *x86_64* ]]; then
      echo "${RED}Unsupported system architecture.${NORMAL}"
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

while getopts ":a:b:f:h" opt; do
  case $opt in
  a)
    echo "Option -a: $OPTARG"
    ;;
  b)
    echo "Option -b: $OPTARG"
    ;;
  f)
    MODE="force"
    ;;
  h)
    echo "Usage: bootstrap.sh [-f] [-h]"
    exit 0
    ;;
  \?)
    # If the user provides an invalid option, display an error message and exit
    echo "Invalid option: -$OPTARG"
    exit 1
    ;;
  :)
    # If the user provides an option without an argument, display an error message and exit
    echo "Option -$OPTARG requires an argument"
    exit 1
    ;;
  esac
done

# Shift the options to the left so the remaining arguments are stored in $@
shift $((OPTIND - 1))

# Do something with the remaining arguments
echo "Remaining arguments: $*"

if [[ $MODE == "force" ]]; then
  rm -rf "$HOME"/dotfiles
  bootstrap
else
  echo "${RED}This will overwrite existing files in your home directory. Are you sure? (y/n)${NORMAL}"
  read -r
  if [[ $REPLY =~ ^[Yy] ]]; then
    if [ -d "$HOME"/dotfiles ]; then
      echo "${YELLOW}You already have dotfiles installed.${NORMAL}"
      echo "${GREEN}Please remove $HOME/dotfiles if you want to re-install.${NORMAL}"
      exit
    else
      setup_dotfiles
      bootstrap
    fi
  else
    echo "${YELLOW}Aborting...${NORMAL}"
  fi
fi
