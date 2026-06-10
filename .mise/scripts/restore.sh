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

  # Agent prompt files are generated, not Mackup-managed (see modules/agents/).
  # Restore semantics: make the system match the repository.
  bash "$(dirname "${BASH_SOURCE[0]}")/../tasks/agents.sh" --force
}

if dotfiles_confirm_force "mise run restore [--force]" \
  "Restore dotfiles from Mackup now?" "$@"; then
  run_restore
else
  exit_status=$?
  [ "$exit_status" -eq 1 ] || exit "$exit_status"
  gum log --level info "Cancelled."
fi
