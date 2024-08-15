#!/bin/bash

#===============================================================================
# TODO
#===============================================================================
SYSTEM_ARCH=$(uname -m)

case "$OSTYPE" in
darwin*)
  case $SYSTEM_ARCH in
  arm64*)
    SYSTEM_TYPE="mac_arm64"
    ;;
  x86_64*)
    SYSTEM_TYPE="mac_x86_64"
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac
  ;;
linux*)
  case $SYSTEM_ARCH in
  x86_64*)
    SYSTEM_TYPE="linux_x86_64"
    ;;
  *armv7l*)
    SYSTEM_TYPE="raspberry"
    ;;
  *)
    SYSTEM_TYPE="unknown"
    ;;
  esac
  ;;
msys*)
  SYSTEM_TYPE="unknown"
  ;;
*)
  SYSTEM_TYPE="unknown"
  ;;
esac

export SYSTEM_TYPE

#===============================================================================
# 👇 zprof
# 👇 在 ~/.zshrc 的头部加上这个，加载 profile 模块
#===============================================================================
# zmodload zsh/zprof

#===============================================================================
# 👇 script initialization guard
#===============================================================================
RED="$(tput setaf 1)"

if [ -z "$_INIT_SH_LOADED" ]; then
  _INIT_SH_LOADED=1
else
  return
fi

#===============================================================================
# 👇 custom
#===============================================================================
ZSH_CUSTOM=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}

if type brew &>/dev/null; then
  # custom completions (Oh-My-Zsh will call compinit for you) (should)
  # https://docs.brew.sh/Shell-Completion
  FPATH="$(brew --prefix)/share/zsh/site-functions:${FPATH}"
  FPATH="$HOME/dotfiles/config/shell/completions:$FPATH"
  autoload -Uz compinit
  compinit -u
fi

#===============================================================================
# 👇 env
#===============================================================================
case $SYSTEM_TYPE in
mac_arm64 | mac_x86_64 | linux_x86_64 | raspberry)
  if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
      local config_files=(
        "$HOME/dotfiles/config/shell/env.zsh"
        "$HOME/dotfiles/config/shell/env_private.zsh"
        "$HOME/dotfiles/config/shell/functions/ai.zsh"
        "$HOME/dotfiles/config/shell/functions/roam.zsh"
        "$HOME/dotfiles/config/shell/functions/misc.zsh"
        "$HOME/dotfiles/config/shell/aliases.zsh"
        "$HOME/dotfiles/config/shell/completions.zsh"
      )

      for file in "${config_files[@]}"; do
        if [ -f "$file" ]; then
          . "$file"
        fi
      done
    fi
  fi
  ;;
unknown)
  echo "${RED}Unsupported system architecture.${NORMAL}"
  ;;
esac

#===============================================================================
# 👇 zprof
#===============================================================================
# zprof
