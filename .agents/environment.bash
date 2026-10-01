#!/usr/bin/env bash
# Sourced by the orb's login profile; do not change the caller's shell options.
_dotfiles_orb_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# A nested or exec'd login can reset PATH. Keep the guard shell-local so every
# new login receives the complete mise environment, even when it reuses a PID.
if [[ -z "${DOTFILES_ORB_ENV:-}" ]]; then
  case "$PWD" in
    "$_dotfiles_orb_root"|"$_dotfiles_orb_root"/*)
      export PATH="$HOME/.local/bin:$PATH"
      if _dotfiles_orb_env="$(mise env --shell bash)"; then
        eval "$_dotfiles_orb_env"
        DOTFILES_ORB_ENV=1
        export -n DOTFILES_ORB_ENV
      fi
      ;;
  esac
fi
unset _dotfiles_orb_root _dotfiles_orb_env
