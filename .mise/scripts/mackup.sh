#!/usr/bin/env bash

# Shared Mackup helpers for mise tasks.
# Assumes callers have already `cd`ed to the repository root.

dotfiles_has_op_session() {
  command -v op &>/dev/null && op account list &>/dev/null
}

dotfiles_generate_home_zshenv() {
  [ "${DOTFILES_HOME_ZSHENV_READY:-0}" = 1 ] && return 0

  if dotfiles_has_op_session; then
    gum spin --title "Injecting ~/.zshenv..." -- \
      op inject --in-file home/.zshenv.tpl \
                --out-file home/.zshenv \
                --force
    DOTFILES_HOME_ZSHENV_READY=1
  elif [ -f home/.zshenv ]; then
    gum log --level warn "1Password CLI not signed in — using existing home/.zshenv"
    DOTFILES_HOME_ZSHENV_READY=1
  else
    gum log --level warn "1Password CLI not signed in — home/.zshenv was not generated"
  fi
}

dotfiles_restore_mackup_without_mise_self() {
  local title="$1"
  shift

  # Do not restore Mackup's `mise` app while this task is running under mise.
  # Replacing ~/.config/mise/config.toml or mise.lock mid-task can make the
  # task runner itself disappear from under the running process.
  local cfg status
  cfg=$(mktemp "$PWD/.mackup-restore.XXXXXX")
  awk '$0 != "mise" { print }' modules/mackup/.mackup.cfg >"$cfg"

  if gum spin --title "$title" -- uvx mackup --config-file "$cfg" restore "$@"; then
    rm -f "$cfg"
    return 0
  else
    status=$?
    rm -f "$cfg"
    return "$status"
  fi
}

dotfiles_mackup_backup() {
  dotfiles_run "Running mackup backup..." uvx mackup backup --force
}

dotfiles_ensure_mackup_link() {
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
