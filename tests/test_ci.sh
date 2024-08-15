#!/bin/bash

set -e

echo "Testing Git"
test -x "$(which git)"

echo "Testing Go"
test -x "$(which go version)"

echo "Testing OMZ"
test -d "$HOME"/.oh-my-zsh

echo "Testing Homebrew"
test -x "$(which brew)"

echo "Testing Mackup"
test -f "$HOME"/.zprofile
test -f "$HOME"/.zshrc
