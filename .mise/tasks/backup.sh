#!/usr/bin/env bash
#MISE description="Backup your dotfiles"

set -euo pipefail

# shellcheck source=.mise/scripts/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/common.sh"

dotfiles_cd_root
dotfiles_require gum uvx

# shellcheck source=.mise/scripts/mackup.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/mackup.sh"

if dotfiles_confirm_or_force "mise run backup [--force]" \
  "Backup current dotfiles into the repository now?" "$@"; then
  dotfiles_mackup_backup
else
  status=$?
  [ "$status" -eq 1 ] || exit "$status"
  gum log --level info "Cancelled."
fi
