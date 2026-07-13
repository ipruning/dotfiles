# Minimal Bash integration for Linux hosts.

_dotfiles_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"

_dotfiles_prepend_path() {
  _dotfiles_candidate="$1"
  if [ -d "$_dotfiles_candidate" ]; then
    case ":$PATH:" in
      *":$_dotfiles_candidate:"*) ;;
      *) PATH="$_dotfiles_candidate:$PATH" ;;
    esac
  fi
}

_dotfiles_prepend_path "$_dotfiles_repo_root/generated/bin"
_dotfiles_prepend_path "$_dotfiles_repo_root/modules/bin"
_dotfiles_prepend_path "$HOME/.local/bin"
export PATH

case $- in
  *i*)
    if command -v mise >/dev/null 2>&1; then
      eval "$(mise activate bash)"
    fi
    ;;
esac

unset _dotfiles_candidate _dotfiles_repo_root
unset -f _dotfiles_prepend_path
