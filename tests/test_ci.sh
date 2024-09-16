#!/bin/bash

set -e

echo "Testing Homebrew"
test -x "$(which brew)"

echo "Testing Mackup"
test -f "$HOME"/.zprofile
test -f "$HOME"/.zshrc
