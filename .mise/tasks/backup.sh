#!/usr/bin/env bash
#MISE description="Backup your dotfiles"

set -euo pipefail

# shellcheck source=.mise/scripts/task-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/task-lib.sh"

dotfiles_enter_repo
dotfiles_require_commands gum uvx

# shellcheck source=.mise/scripts/mackup-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/mackup-lib.sh"

if dotfiles_confirm_force "mise run backup [--force]" \
  "Backup current dotfiles into the repository now?" "$@"; then
  dotfiles_mackup_backup_force
else
  exit_status=$?
  [ "$exit_status" -eq 1 ] || exit "$exit_status"
  gum log --level info "Cancelled."
fi
