#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=.mise/scripts/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

dotfiles_cd_root
dotfiles_require gum uvx

# shellcheck source=.mise/scripts/mackup.sh
source "$(dirname "${BASH_SOURCE[0]}")/mackup.sh"

run_restore() {
  dotfiles_generate_home_zshenv
  dotfiles_restore_mackup_without_mise_self "Running mackup restore..." --force
}

if dotfiles_confirm_or_force "mise run restore [--force]" \
  "Restore dotfiles from Mackup now?" "$@"; then
  run_restore
else
  status=$?
  [ "$status" -eq 1 ] || exit "$status"
  gum log --level info "Cancelled."
fi
