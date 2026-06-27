# shellcheck shell=bash

dotfiles_log() {
  local level="$1" message="$2"

  if command -v gum &>/dev/null; then
    gum log --level "$level" "$message"
    return
  fi

  local level_upper
  level_upper="$(printf "%s" "$level" | tr '[:lower:]' '[:upper:]')"
  printf '[%s] [%s] %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$level_upper" "$message"
}
