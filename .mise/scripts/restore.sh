#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=.mise/scripts/task-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/task-lib.sh"

dotfiles_enter_repo
dotfiles_require_commands gum uvx

# shellcheck source=.mise/scripts/mackup-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/mackup-lib.sh"

run_restore() {
  dotfiles_prepare_private_zshenv
  dotfiles_mackup_restore_safely "Running mackup restore..." --force
}

if dotfiles_confirm_force "mise run restore [--force]" \
  "Restore dotfiles from Mackup now?" "$@"; then
  run_restore
else
  exit_status=$?
  [ "$exit_status" -eq 1 ] || exit "$exit_status"
  gum log --level info "Cancelled."
fi
