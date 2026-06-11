#!/usr/bin/env bash

# Shared Mackup helpers for mise tasks.
# Assumes callers have already sourced task-lib.sh and `cd`ed to the repository root.

dotfiles_prepare_private_zshenv() {
  [ "${DOTFILES_PRIVATE_ZSHENV_READY:-0}" = 1 ] && return 0

  if command -v op &>/dev/null; then
    local inject_timeout="${DOTFILES_OP_INJECT_TIMEOUT:-20}"
    gum log --level info "Injecting ~/.zshenv.private.zsh..."
    if dotfiles_run_with_timeout "$inject_timeout" \
      op inject --in-file home/.zshenv.private.tpl.zsh \
                --out-file home/.zshenv.private.zsh \
                --force; then
      DOTFILES_PRIVATE_ZSHENV_READY=1
      return 0
    fi

    if [ -f home/.zshenv.private.zsh ]; then
      gum log --level warn "1Password injection failed — using existing home/.zshenv.private.zsh"
      DOTFILES_PRIVATE_ZSHENV_READY=1
      return 0
    fi

    gum log --level warn "1Password injection failed — private zsh env was not generated"
  elif [ -f home/.zshenv.private.zsh ]; then
    gum log --level warn "1Password CLI not found — using existing home/.zshenv.private.zsh"
    DOTFILES_PRIVATE_ZSHENV_READY=1
  else
    gum log --level warn "1Password CLI not found — private zsh env was not generated"
  fi
}

dotfiles_mackup_restore_safely() {
  local title="$1"
  shift

  dotfiles_configure_mackup_symlinks

  gum log --level info "$title"
  dotfiles_run_with_timeout "${DOTFILES_MACKUP_TIMEOUT:-300}" uvx mackup restore "$@"
}

dotfiles_mackup_backup_force() {
  dotfiles_configure_mackup_symlinks

  gum log --level info "Running mackup backup..."
  dotfiles_run_with_timeout "${DOTFILES_MACKUP_TIMEOUT:-300}" uvx mackup backup --force
}

dotfiles_configure_mackup_symlinks() {
  DOTFILES_MACKUP_SYMLINKS_CHANGED=0

  local status

  if dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup" "$HOME/.mackup"; then
    DOTFILES_MACKUP_SYMLINKS_CHANGED=1
  else
    status=$?
    [ "$status" -eq 1 ] || return "$status"
  fi

  if dotfiles_ensure_mackup_symlink "$PWD/modules/mackup/.mackup.cfg" "$HOME/.mackup.cfg"; then
    DOTFILES_MACKUP_SYMLINKS_CHANGED=1
  else
    status=$?
    [ "$status" -eq 1 ] || return "$status"
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

    gum log --level warn "$link points to $(readlink "$link"); relinking to $target"
    ln -sfn "$target" "$link"
    return 0
  fi

  if [ -e "$link" ]; then
    gum log --level warn "$link exists and is not a symlink; skipping (move it aside to fix)"
    return 2
  fi

  ln -s "$target" "$link"
  return 0
}
