# shellcheck shell=bash

dotfiles_write_if_available() {
  local cmd="$1" output="$2"
  shift 2

  command -v "$cmd" &>/dev/null || return 0
  dotfiles_run_with_timeout "${DOTFILES_OPTIONAL_COMMAND_TIMEOUT:-15}" "$@" >"$output" 2>/dev/null \
    || dotfiles_log warn "$cmd generation failed: $output"
}
