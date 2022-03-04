#!/usr/bin/env bash

# set -e

source "$HOME"/dotfiles/bin/csys # check SYSTEM_OS, SYSTEM_ARCH
echo "$ZSH_NAME" "$ZSH_VERSION"

echo "Testing"
echo "Testing Git"
test -x "$(which git)"

case "$SYSTEM_TYPE" in
mac*)
  echo "Testing Homebrew"
  test -x "$(which brew)"
  python --version | grep --fixed-strings "Python 3.10.2"
  "$(brew --prefix)"/bin/zsh -c "python --version" | grep --fixed-strings "Python 3.10.2"
  which python | rg "shims"
  ;;
*)
  echo "unknown $SYSTEM_ARCH"
  ;;
esac

echo "Testing Mackup"
cat "$HOME"/.zshrc
test -f "$HOME"/.zshrc
test -f "$HOME"/.zprofile