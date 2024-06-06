#!/usr/bin/env bash

set -e

echo "Testing Git"
test -x "$(which git)"

echo "Testing Go"
test -x "$(which go version)"

echo "Testing ZSH"
test -x "$(which zsh)"

test -d "$HOME"/.oh-my-zsh

cat "$HOME"/.zshrc
test -f "$HOME"/.zshrc

cat "$HOME"/.zprofile
test -f "$HOME"/.zprofile

echo "Testing Homebrew"
test -x "$(which brew)"

echo "Testing Mackup"
test -f "$HOME"/.zshrc
