#!/usr/bin/env bash
#MISE description="Restore your dotfiles"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

generate_home_zshenv() {
  # Mackup restores `~/.zshenv` from ignored `home/.zshenv`. That file contains
  # secrets, so the tracked source is `home/.zshenv.tpl`; generate it before
  # restore to keep the zsh PATH bootstrap and injected secrets in sync.
  if command -v op &>/dev/null && op account list &>/dev/null; then
    gum spin --title "Injecting ~/.zshenv..." -- \
      op inject --in-file home/.zshenv.tpl \
                --out-file home/.zshenv
  elif [ -f home/.zshenv ]; then
    gum log --level warn "1Password CLI not signed in — restoring existing home/.zshenv"
  else
    gum log --level warn "1Password CLI not signed in — ~/.zshenv will not be restored from Mackup"
  fi
}

if [[ "${1:-}" == "--force" ]]; then
  generate_home_zshenv
  gum spin --title "Running mackup restore..." -- uvx mackup restore --force
  exit 0
fi

if gum confirm "Are you sure you want to run mackup restore (force)?" \
  --prompt.foreground="15" \
  --selected.foreground="0" --selected.background="2" \
  --unselected.foreground="250" --unselected.background="238"; then
  generate_home_zshenv
  gum spin --title "Running mackup restore..." -- uvx mackup restore --force
else
  gum log --level info "Cancelled."
  exit 0
fi
