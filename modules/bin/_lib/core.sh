# shellcheck shell=bash

dotfiles_enter_repo() {
  cd "$(git rev-parse --show-toplevel)" || return
}

dotfiles_require_commands() {
  local missing=() cmd
  for cmd in "$@"; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done

  if [ ${#missing[@]} -gt 0 ]; then
    if declare -F dotfiles_log >/dev/null 2>&1; then
      dotfiles_log error "Missing required command(s): ${missing[*]}"
    elif command -v gum &>/dev/null; then
      gum log --level error "Missing required command(s): ${missing[*]}"
    else
      printf 'ERROR Missing required command(s): %s\n' "${missing[*]}" >&2
    fi
    return 127
  fi
}
