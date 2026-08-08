# Minimal Bash integration for Linux hosts.

_dotfiles_init_source=${BASH_SOURCE[0]}
_dotfiles_repo_root=$(cd "$(dirname "$_dotfiles_init_source")/../.." && pwd -P)
_dotfiles_functions_dir="$_dotfiles_repo_root/generated/functions"

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
    if command -v starship >/dev/null 2>&1 && [ -f "$_dotfiles_functions_dir/_starship.bash" ]; then
      . "$_dotfiles_functions_dir/_starship.bash"
    fi
    alias ..='cd ..'
    alias ...='cd ../..'
    if command -v atuin >/dev/null 2>&1 && [ -f "$_dotfiles_functions_dir/_atuin.bash" ]; then
      . "$_dotfiles_functions_dir/_atuin.bash"
    fi
    if command -v zoxide >/dev/null 2>&1 && [ -f "$_dotfiles_functions_dir/_zoxide.bash" ]; then
      . "$_dotfiles_functions_dir/_zoxide.bash"
    fi
    # Activate mise after integrations that rewrite PROMPT_COMMAND so its
    # dynamic environment hook remains installed.
    if [ -x "$HOME/.local/bin/mise" ] && [ ! -L "$HOME/.local/bin/mise" ] && \
      [ -f "$_dotfiles_functions_dir/_mise.bash" ]; then
      . "$_dotfiles_functions_dir/_mise.bash"
    fi
    bind '"\C-w": "\e\C-?"'
    # Herdr panes retain SSH_TTY, so HERDR_ENV is the recursion boundary.
    # HERDR_SSH_AUTOSTART=0 leaves an explicit recovery path to the shell.
    if [ -n "${SSH_TTY:-}" ] && [ -z "${HERDR_ENV:-}" ] && \
      [ "${HERDR_SSH_AUTOSTART:-1}" != 0 ] && \
      herdr --version >/dev/null 2>&1; then
      exec herdr
    fi
    ;;
esac

unset _dotfiles_candidate
unset _dotfiles_functions_dir _dotfiles_repo_root _dotfiles_init_source
unset -f _dotfiles_prepend_path
