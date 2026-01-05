#!/usr/bin/env bash
#MISE description="Restore your dotfiles"

set -euo pipefail

command -v git >/dev/null 2>&1 || { echo "Error: git not found" >&2; exit 1; }
command -v gum >/dev/null 2>&1 || exit 1
command -v mise >/dev/null 2>&1 || exit 1
command -v uv >/dev/null 2>&1 || exit 1

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "Error: not inside a git repo" >&2; exit 1; }
cd "$REPO_ROOT" || exit 1

gum confirm "Are you sure you want to run mackup restore(force)?" && uvx mackup restore --force
