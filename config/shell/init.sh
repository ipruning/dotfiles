#!/bin/bash

#===============================================================================
# 👇 _INIT_SH_LOADED
#===============================================================================
if [ -z "$_INIT_SH_LOADED" ]; then
  _INIT_SH_LOADED=1
else
  return
fi

#===============================================================================
# 👇 Check system architecture
#===============================================================================
# if [[ "$(sysctl -a | grep machdep.cpu.brand_string)" == *Apple* ]]; then
#   echo test
# fi

SYSTEM_ARCH=$(uname -m)

case $SYSTEM_ARCH in
arm64*)
  # echo "arm64"
  ;;
x86_64*)
  # echo "x86_64"
  ;;
*)
  echo "unknown: $(uname -m)"
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
