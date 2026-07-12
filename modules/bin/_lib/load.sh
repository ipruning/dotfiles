# shellcheck shell=bash

if [[ -n "${DOTFILES_LIB_LOADED:-}" ]]; then
  return 0
fi

DOTFILES_LIB_LOADED=1
DOTFILES_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=modules/bin/_lib/core.sh
source "$DOTFILES_LIB_DIR/core.sh"
# shellcheck source=modules/bin/_lib/log.sh
source "$DOTFILES_LIB_DIR/log.sh"
