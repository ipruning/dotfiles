#!/usr/bin/env bash

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# mise's standalone-script runner can lose the direct child status while this
# task runs gum + Mackup restore. Keep a stable parent process for mise to wait
# on, and run the actual restore in a normal bash child.
if [[ ${DOTFILES_RESTORE_CHILD:-} != 1 ]]; then
  DOTFILES_RESTORE_CHILD=1 bash "$0" "$@"
  exit $?
fi

generate_home_zshenv() {
  # Mackup restores `~/.zshenv` from ignored `home/.zshenv`. That file contains
  # secrets, so the tracked source is `home/.zshenv.tpl`; generate it before
  # restore to keep the zsh PATH bootstrap and injected secrets in sync.
  if command -v op &>/dev/null && op account list &>/dev/null; then
    gum spin --title "Injecting ~/.zshenv..." -- \
      op inject --in-file home/.zshenv.tpl \
                --out-file home/.zshenv \
                --force
  elif [ -f home/.zshenv ]; then
    gum log --level warn "1Password CLI not signed in — restoring existing home/.zshenv"
  else
    gum log --level warn "1Password CLI not signed in — ~/.zshenv will not be restored from Mackup"
  fi
}

restore_mackup_without_mise_self() {
  # Do not restore Mackup's `mise` app while this task is running under mise.
  # Replacing ~/.config/mise/config.toml or mise.lock mid-task can make the
  # mise task runner report "no exit status" even when Mackup itself succeeds.
  local cfg status
  cfg=$(mktemp "$PWD/.mackup-restore.XXXXXX")
  awk '$0 != "mise" { print }' modules/mackup/.mackup.cfg >"$cfg"

  if gum spin --title "Running mackup restore..." -- uvx mackup --config-file "$cfg" restore "$@"; then
    rm -f "$cfg"
    return 0
  else
    status=$?
    rm -f "$cfg"
    return "$status"
  fi
}

if [[ "${1:-}" == "--force" ]]; then
  generate_home_zshenv
  restore_mackup_without_mise_self --force
  exit 0
fi

if gum confirm "Are you sure you want to run mackup restore (force)?" \
  --prompt.foreground="15" \
  --selected.foreground="0" --selected.background="2" \
  --unselected.foreground="250" --unselected.background="238"; then
  generate_home_zshenv
  restore_mackup_without_mise_self --force
else
  gum log --level info "Cancelled."
  exit 0
fi
