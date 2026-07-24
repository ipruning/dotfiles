# Minimal Bash integration for Linux hosts.

_dotfiles_prepend_path() {
  _dotfiles_candidate="$1"
  if [ -d "$_dotfiles_candidate" ]; then
    case ":$PATH:" in
      *":$_dotfiles_candidate:"*) ;;
      *) PATH="$_dotfiles_candidate:$PATH" ;;
    esac
  fi
}

_dotfiles_prepend_path "$HOME/.local/bin"
_dotfiles_prepend_path "$HOME/.local/share/mise/shims"
export PATH

case $- in
  *i*)
    if [ -x "$HOME/.local/bin/mise" ] && [ ! -L "$HOME/.local/bin/mise" ]; then
      eval "$("$HOME/.local/bin/mise" activate bash)"
    fi
    if command -v starship >/dev/null 2>&1; then
      if _dotfiles_starship_init="$(starship init bash 2>/dev/null)"; then
        eval "$_dotfiles_starship_init"
      fi
      unset _dotfiles_starship_init
    fi
    ;;
esac

unset _dotfiles_candidate
unset -f _dotfiles_prepend_path
