# .zshenv is read by every zsh: login, interactive, scripts, and `zsh -c`.
# Keep it silent and cheap. Do not run `mise activate`, `brew shellenv`,
# compinit, prompts, plugins, network calls, or anything that can print output.

typeset -U path

# Single source of truth for the base executable path.
#
# Why here instead of `.zprofile`: many agents, IDEs, and automations execute
# non-login zsh commands, so `.zprofile` is never read. Shims are enough for
# non-interactive mise usage; interactive shells get full `mise activate` from
# the cached script sourced by `.zshrc`.
_dotfiles_core_path() {
  if [[ ${OSTYPE:-} == darwin* ]]; then
    # Intel Homebrew, Apple Silicon Homebrew. Add bin and sbin when present so
    # restored dotfiles work across Macs without conditional edits.
    [[ -d /usr/local/sbin ]] && path=(/usr/local/sbin $path)
    [[ -d /usr/local/bin ]] && path=(/usr/local/bin $path)
    [[ -d /opt/homebrew/sbin ]] && path=(/opt/homebrew/sbin $path)
    [[ -d /opt/homebrew/bin ]] && path=(/opt/homebrew/bin $path)
    # Repository command collections are a macOS-only surface. Keeping them
    # out of the cross-platform mise [env] config means restoring that config
    # on Linux can never shadow system tools again (iproute2 ss).
    [[ -d "$HOME/dotfiles/modules/bin" ]] && path=("$HOME/dotfiles/modules/bin" $path)
    [[ -d "$HOME/dotfiles/generated/bin" ]] && path=("$HOME/dotfiles/generated/bin" $path)
  fi

  # mise's installer and other per-user executables use this cross-platform
  # location. It must be available before interactive initialization so a
  # direct Linux Zsh session can discover mise without first passing through Bash.
  [[ -d "$HOME/.local/bin" ]] && path=("$HOME/.local/bin" $path)

  # Static equivalent of `mise activate zsh --shims`. Prefer this over calling
  # `mise` here because this file must also bootstrap shells where `mise` is not
  # on PATH yet.
  [[ -d "$HOME/.local/share/mise/shims" ]] && path=("$HOME/.local/share/mise/shims" $path)

  export PATH
}

_dotfiles_core_path

# Optional machine/private environment. Materialize it deliberately from
# `reference/.zshenv.private.tpl.zsh`; repository tasks never inject secrets.
# Missing private env must not break PATH bootstrap or non-interactive shells.
[[ -r "$HOME/.zshenv.private.zsh" ]] && source "$HOME/.zshenv.private.zsh"
