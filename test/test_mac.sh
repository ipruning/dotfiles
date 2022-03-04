#!/usr/bin/env bash

set -e

echo "Testing"

test -x "$(which git)"
test -x "$(which code)"
python --version | rg "Python 3.10.2"
which python | rg "shims"

test -d "$HOME"/dotfiles
echo "Testing ZSH"
test -x "$(which zsh)"
test -d "$HOME"/.oh-my-zsh
echo "Testing Homebrew"
test -x "$(which brew)"
echo "Testing Mackup"
test -f "$HOME"/.zshrc
