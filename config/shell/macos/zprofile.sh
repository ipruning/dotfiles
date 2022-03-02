#!/bin/bash

# homebrew shell env
case $(uname -m) in
arm64*)
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ;;
x86_64*)
  eval "$(/usr/local/homebrew/bin/brew shellenv)"
  ;;
*)
  echo "unknown: $(uname -m)"
  ;;
esac

# homebrew & pipx & other binaries
export PATH="$PATH:${HOME}/.local/bin"
