# shellcheck shell=bash

dotfiles_run_with_timeout() {
  local timeout_seconds="$1"
  shift

  "$@" &
  local command_pid=$!

  (
    sleep "$timeout_seconds" &
    local sleep_pid=$!
    trap 'kill "$sleep_pid" 2>/dev/null || true; exit 0' TERM INT

    if wait "$sleep_pid" 2>/dev/null && kill -0 "$command_pid" 2>/dev/null; then
      kill "$command_pid" 2>/dev/null || true
      sleep 1
      kill -9 "$command_pid" 2>/dev/null || true
    fi
  ) &
  local timer_pid=$!

  local exit_status=0
  if wait "$command_pid" 2>/dev/null; then
    exit_status=0
  else
    exit_status=$?
  fi

  kill "$timer_pid" 2>/dev/null || true
  wait "$timer_pid" 2>/dev/null || true
  return "$exit_status"
}

dotfiles_spin() {
  local title="$1"
  shift
  gum spin --title "$title" -- "$@"
}

dotfiles_run_visible() {
  local title="$1" timeout_seconds="$2"
  shift 2

  if [ -t 1 ] && command -v gum &>/dev/null; then
    gum spin --show-error --title "$title" --timeout="${timeout_seconds}s" -- "$@"
  else
    dotfiles_run_with_timeout "$timeout_seconds" "$@"
  fi
}
