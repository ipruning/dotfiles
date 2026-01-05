#!/usr/bin/env bash
#
# Shared helpers for mise task scripts.
#
# Usage (in task scripts):
#   set -euo pipefail
#   SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
#   # shellcheck source=/dev/null
#   source "$SCRIPT_DIR/_lib.sh"
#

set -euo pipefail

_color_blue() { printf "\033[34m%s\033[0m\n" "$*"; }
_color_red() { printf "\033[31m%s\033[0m\n" "$*"; }

log_info() { _color_blue "==> $*"; }
log_warn() { printf "\033[33m==> %s\033[0m\n" "$*"; }
log_error() { _color_red "==> $*"; }

die() { log_error "$*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "$1 not found"
}

script_dir() {
  cd -- "$(dirname -- "${BASH_SOURCE[1]}")" && pwd
}

repo_root() {
  local d
  d="$(script_dir)"
  cd -- "$d/../.." && pwd
}
