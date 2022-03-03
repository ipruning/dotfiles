#!/bin/bash

#===============================================================================
# 👇 INIT
#===============================================================================
RED="$(tput setaf 1)"

if [ -z "$_INIT_SH_LOADED" ]; then
  _INIT_SH_LOADED=1
else
  return
fi

# if [[ "$(sysctl -a | grep machdep.cpu.brand_string)" == *Apple* ]]; then
#   echo test
# fi

# if [[ $(uname) == 'Darwin' ]]; then
#   platform='darwin'
# else
#   platform='linux'
# fi
# if [[ $(arch) == 'arm64' ]]; then
#   arch='arm64'
# else
#   arch='amd64'
# fi

SYSTEM_ARCH=$(uname -m)

case "$OSTYPE" in
darwin*)
  case $SYSTEM_ARCH in
  arm64*)
    SYSTEM_TYPE="macOS_arm64"
    ;;
  x86_64*)
    SYSTEM_TYPE="macOS_x86_64"
    ;;
  *)
    echo "${RED}Unsupported system architecture.${NORMAL}"
    ;;
  esac
  ;;
linux*)
  if [[ "$(uname -m)" == *armv7l* ]]; then
    SYSTEM_TYPE="raspberry"
  else
    echo "${RED}Unsupported system architecture.${NORMAL}"
    SYSTEM_TYPE="unknown"
  fi
  ;;
msys*)
  echo "${RED}Unsupported system architecture.${NORMAL}"
  ;;
*)
  echo "${RED}unknown: $OSTYPE${NORMAL}"
  SYSTEM_TYPE="unknown"
  ;;
esac

#===============================================================================
# 👇 zprof
#===============================================================================
# zmodload zsh/zprof # 在 ~/.zshrc 的头部加上这个，加载 profile 模块

#===============================================================================
# 👇 env
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
  # run script for interactive mode of bash/zsh
  if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
    if [ -f "$HOME/dotfiles/config/shell/zsh_env.sh" ]; then
      . "$HOME/dotfiles/config/shell/zsh_env.sh"
    fi
    if [ -f "$HOME/dotfiles/config/shell/zsh_functions.sh" ]; then
      . "$HOME/dotfiles/config/shell/zsh_functions.sh"
    fi
    if [ -f "$HOME/dotfiles/config/shell/zsh_aliases.sh" ]; then
      . "$HOME/dotfiles/config/shell/zsh_aliases.sh"
    fi
    if [ -f "$HOME/dotfiles/config/shell/zsh_completion.sh" ]; then
      . "$HOME/dotfiles/config/shell/zsh_completion.sh"
    fi
  fi
fi

#===============================================================================
# 👇 zprof
#===============================================================================
# zprof
