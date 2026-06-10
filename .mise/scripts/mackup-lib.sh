#!/usr/bin/env bash

# Shared Mackup helpers for mise tasks.
# Assumes callers have already `cd`ed to the repository root.

dotfiles_op_signed_in() {
  command -v op &>/dev/null && op account list &>/dev/null
}

dotfiles_prepare_zshenv() {
  [ "${DOTFILES_ZSHENV_READY:-0}" = 1 ] && return 0

  if dotfiles_op_signed_in; then
    if gum spin --title "Injecting ~/.zshenv..." -- \
      op inject --in-file home/.zshenv.tpl \
                --out-file home/.zshenv \
                --force; then
      DOTFILES_ZSHENV_READY=1
      return 0
    fi

    if [ -f home/.zshenv ]; then
      gum log --level warn "1Password injection failed — using existing home/.zshenv"
      DOTFILES_ZSHENV_READY=1
      return 0
    fi

    gum log --level warn "1Password injection failed — home/.zshenv was not generated"
  elif [ -f home/.zshenv ]; then
    gum log --level warn "1Password CLI not signed in — using existing home/.zshenv"
    DOTFILES_ZSHENV_READY=1
  else
    gum log --level warn "1Password CLI not signed in — home/.zshenv was not generated"
  fi
}

dotfiles_mackup_restore_safely() {
  local title="$1"
  shift

  # Do not restore Mackup's `mise` app while this task is running under mise.
  # Replacing ~/.config/mise/config.toml or mise.lock mid-task can make the
  # task runner itself disappear from under the running process.
  local mackup_config exit_status
  mackup_config=$(mktemp "$PWD/.mackup-restore.XXXXXX")
  awk '$0 != "mise" { print }' modules/mackup/.mackup.cfg >"$mackup_config"

  if gum spin --title "$title" -- uvx mackup --config-file "$mackup_config" restore "$@"; then
    rm -f "$mackup_config"
    return 0
  else
    exit_status=$?
    rm -f "$mackup_config"
    return "$exit_status"
  fi
}

dotfiles_mackup_backup_force() {
  dotfiles_spin "Running mackup backup..." uvx mackup backup --force
}

dotfiles_ensure_mackup_symlink() {
  local target="$1" link="$2"

  if [ -L "$link" ]; then
    # Already a symlink — keep as-is to avoid unnecessary churn.
    return 1
  fi
  if [ -e "$link" ]; then
    gum log --level warn "$link exists and is not a symlink; skipping (move it aside to fix)"
    return 1
  fi

  ln -s "$target" "$link"
  return 0
}
