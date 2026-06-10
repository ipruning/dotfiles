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
    # Intel Homebrew, Apple Silicon Homebrew. Add both when present so restored
    # dotfiles work across Macs without conditional edits.
    [[ -d /usr/local/bin ]] && path=(/usr/local/bin $path)
    [[ -d /opt/homebrew/bin ]] && path=(/opt/homebrew/bin $path)
  fi

  # Static equivalent of `mise activate zsh --shims`. Prefer this over calling
  # `mise` here because this file must also bootstrap shells where `mise` is not
  # on PATH yet.
  [[ -d "$HOME/.local/share/mise/shims" ]] && path=("$HOME/.local/share/mise/shims" $path)

  export PATH
}

_dotfiles_core_path

# Optional machine/private environment. This file is generated from
# `home/.zshenv.private.tpl` with `op inject` when 1Password is available.
# Missing private env must not break PATH bootstrap or non-interactive shells.
[[ -r "$HOME/.zshenv.private" ]] && source "$HOME/.zshenv.private"
