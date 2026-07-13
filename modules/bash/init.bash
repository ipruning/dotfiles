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
    if command -v mise >/dev/null 2>&1; then
      eval "$(mise activate bash)"
    fi
    ;;
esac

unset _dotfiles_candidate
unset -f _dotfiles_prepend_path
