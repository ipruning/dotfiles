#!/bin/bash

case $SYSTEM_TYPE in
macOS_arm64 | macOS_x86_64*)
  #===============================================================================
  # 👇 cz completions
  #===============================================================================
  eval "$(register-python-argcomplete cz)"

  #===============================================================================
  # 👇 pipx completions
  #===============================================================================
  eval "$(register-python-argcomplete pipx)"

  #===============================================================================
  # 👇 zoxide completions
  #===============================================================================
  eval "$(zoxide init zsh)"
  ;;
raspberry) ;;

esac

#===============================================================================
# 👇 zsh-completions
# if you are using a custom compinit setup with a ZSH Framework, ensure compinit is below your sourcing of the framework
#===============================================================================
autoload -Uz compinit && compinit
