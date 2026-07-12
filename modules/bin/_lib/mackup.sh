# shellcheck shell=bash

# shellcheck source=modules/bin/_lib/load.sh
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/load.sh"

readonly DOTFILES_MACKUP_SOURCE='git+https://github.com/ipruning/mackup@680f16339402dd82e6e2c1be4f4af41484cc7bc1'

dotfiles_prepare_private_zshenv() {
  [ "${DOTFILES_PRIVATE_ZSHENV_READY:-0}" = 1 ] && return 0

  if command -v op &>/dev/null; then
    local inject_timeout="${DOTFILES_OP_INJECT_TIMEOUT:-20}"
    dotfiles_log info "Injecting ~/.zshenv.private.zsh..."
    if dotfiles_run_with_timeout "$inject_timeout" \
      op inject --in-file home/.zshenv.private.tpl.zsh \
                --out-file home/.zshenv.private.zsh \
                --force; then
      DOTFILES_PRIVATE_ZSHENV_READY=1
      return 0
    fi

    if [ -f home/.zshenv.private.zsh ]; then
      dotfiles_log warn "1Password injection failed — using existing home/.zshenv.private.zsh"
      DOTFILES_PRIVATE_ZSHENV_READY=1
      return 0
    fi

    dotfiles_log warn "1Password injection failed — private zsh env was not generated"
  elif [ -f home/.zshenv.private.zsh ]; then
    dotfiles_log warn "1Password CLI not found — using existing home/.zshenv.private.zsh"
    DOTFILES_PRIVATE_ZSHENV_READY=1
  else
    dotfiles_log warn "1Password CLI not found — private zsh env was not generated"
  fi
}

dotfiles_mackup() {
  dotfiles_run_with_timeout "${DOTFILES_MACKUP_TIMEOUT:-300}" \
    uvx --isolated --from "$DOTFILES_MACKUP_SOURCE" mackup "$@"
}

dotfiles_mackup_restore_plan() {
  dotfiles_mackup --dry-run restore
}

dotfiles_mackup_restore_plan_json() {
  dotfiles_mackup --dry-run --json restore
}

dotfiles_mackup_restore_force() {
  dotfiles_mackup --force restore
}

dotfiles_mackup_backup_force() {
  dotfiles_configure_mackup_symlinks

  dotfiles_log info "Running mackup backup..."
  dotfiles_mackup --force backup
}

# DOTFILES_MACKUP_SYMLINKS_CHANGED is read by modules/bin/dotfiles-init after
# this helper updates Mackup links.
# shellcheck disable=SC2034
dotfiles_configure_mackup_symlinks() {
  DOTFILES_MACKUP_SYMLINKS_CHANGED=0

  local exit_status

  if dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup" "$HOME/.mackup"; then
    DOTFILES_MACKUP_SYMLINKS_CHANGED=1
  else
    exit_status=$?
    [ "$exit_status" -eq 1 ] || return "$exit_status"
  fi

  if dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup.cfg" "$HOME/.mackup.cfg"; then
    DOTFILES_MACKUP_SYMLINKS_CHANGED=1
  else
    exit_status=$?
    [ "$exit_status" -eq 1 ] || return "$exit_status"
  fi

  return 0
}

dotfiles_ensure_mackup_symlink() {
  local target="$1" link="$2"

  if [ -L "$link" ]; then
    if [ "$(readlink "$link")" = "$target" ]; then
      # Already a symlink to this repository — keep as-is to avoid churn.
      return 1
    fi

    dotfiles_log warn "$link points to $(readlink "$link"); relinking to $target"
    ln -sfn "$target" "$link"
    return 0
  fi

  if [ -e "$link" ]; then
    dotfiles_log warn "$link exists and is not a symlink; skipping (move it aside to fix)"
    return 2
  fi

  ln -s "$target" "$link"
  return 0
}
