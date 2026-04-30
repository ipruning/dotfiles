#!/usr/bin/env bash
#MISE description="Restore your dotfiles"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [[ "${1:-}" == "--force" ]]; then
  gum spin --title "Running mackup restore..." -- uvx mackup restore --force
  exit 0
fi

if gum confirm "Are you sure you want to run mackup restore (force)?" \
  --prompt.foreground="15" \
  --selected.foreground="0" --selected.background="2" \
  --unselected.foreground="250" --unselected.background="238"; then
  gum spin --title "Running mackup restore..." -- uvx mackup restore --force
else
  gum log --level info "Cancelled."
  exit 0
fi
