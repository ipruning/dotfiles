# shellcheck shell=bash

dotfiles_confirm_force() {
  local usage="$1"
  local prompt="$2"
  shift 2

  if [[ "${1:-}" == "--force" ]]; then
    shift
    if [[ $# -gt 0 ]]; then
      dotfiles_log error "Usage: $usage"
      return 2
    fi
    return 0
  fi

  if [[ $# -gt 0 ]]; then
    dotfiles_log error "Usage: $usage"
    return 2
  fi

  gum confirm "$prompt" \
    --prompt.foreground="15" \
    --selected.foreground="0" --selected.background="2" \
    --unselected.foreground="250" --unselected.background="238"
}
