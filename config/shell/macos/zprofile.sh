#!/bin/bash

# homebrew shell env
arch_check=$(/usr/bin/arch)
case $arch_check in
  arm64*)
    eval "$(/opt/homebrew/bin/brew shellenv)" 
  ;;
  i386*)
    echo "TODO"
  ;;
  *)
    echo "TODO"
  ;;
esac

# homebrew & pipx binaries
export PATH="$PATH:${HOME}/.local/bin"
