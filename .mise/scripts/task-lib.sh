#!/usr/bin/env bash

# Shared helpers for dotfiles mise tasks.
# Keep this file small: it is sourced by interactive and non-interactive tasks.

dotfiles_enter_repo() {
  cd "$(git rev-parse --show-toplevel)" || return
}

dotfiles_require_commands() {
  local missing=() cmd
  for cmd in "$@"; do
    command -v "$cmd" &>/dev/null || missing+=("$cmd")
  done

  if [ ${#missing[@]} -gt 0 ]; then
    if command -v gum &>/dev/null; then
      gum log --level error "Missing required command(s): ${missing[*]}"
    else
      printf 'ERROR Missing required command(s): %s\n' "${missing[*]}" >&2
    fi
    return 127
  fi
}

dotfiles_spin() {
  local title="$1"
  shift
  gum spin --title "$title" -- "$@"
}

dotfiles_confirm_force() {
  local usage="$1"
  local prompt="$2"
  shift 2

  if [[ "${1:-}" == "--force" ]]; then
    shift
    if [[ $# -gt 0 ]]; then
      gum log --level error "Usage: $usage"
      return 2
    fi
    return 0
  fi

  if [[ $# -gt 0 ]]; then
    gum log --level error "Usage: $usage"
    return 2
  fi

  gum confirm "$prompt" \
    --prompt.foreground="15" \
    --selected.foreground="0" --selected.background="2" \
    --unselected.foreground="250" --unselected.background="238"
}

dotfiles_write_if_available() {
  local cmd="$1" output="$2"
  shift 2

  command -v "$cmd" &>/dev/null || return 0
  "$@" >"$output" 2>/dev/null || gum log --level warn "$cmd generation failed: $output"
}
