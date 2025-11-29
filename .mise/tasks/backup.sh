#!/usr/bin/env bash
#MISE description="Backup your dotfiles"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

command -v git >/dev/null 2>&1 || exit 1
command -v gum >/dev/null 2>&1 || exit 1
command -v mise >/dev/null 2>&1 || exit 1
command -v uv >/dev/null 2>&1 || exit 1

gum confirm "Are you sure you want to run up?" && up

gum confirm "Are you sure you want to run mackup backup (force)?" && uvx mackup backup --force
