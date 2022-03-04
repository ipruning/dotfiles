#!/bin/zsh

set -e

test -d "$HOME"/dotfiles

echo "Testing"
echo "Testing Git"
test -x "$(which git)"
echo "Testing VS Code"
test -x "$(which code)"
echo "Testing Python"
python --version | rg "Python 3.10.2"
which python | rg "shims"
echo "Testing ZSH"
test -x "$(which zsh)"
test -d "$HOME"/.oh-my-zsh
echo "Testing Homebrew"
test -x "$(which brew)"
echo "Testing Mackup"
test -f "$HOME"/.zshrc
