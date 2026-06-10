#!/usr/bin/env bash
#MISE description="Sync plugins, completions, functions, Skillshare, and host inventories"

set -euo pipefail

# shellcheck source=.mise/scripts/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

dotfiles_cd_root
dotfiles_require gum git

C="generated/completions"
F="generated/functions"

sync_vendor_plugins() {
  gum log --level info "Syncing vendor plugins (git pull)..."

  if [ ! -d generated/plugins ]; then
    gum log --level warn "generated/plugins not found; skipping"
    return 0
  fi

  shopt -s nullglob
  local plugin_dir name branch
  for plugin_dir in generated/plugins/*; do
    [ -d "$plugin_dir" ] || continue
    git -C "$plugin_dir" rev-parse --is-inside-work-tree &>/dev/null || continue

    name="$(basename "$plugin_dir")"

    if ! git -C "$plugin_dir" remote get-url origin &>/dev/null; then
      gum log --level warn "$name (no origin remote; skipping)"
      continue
    fi

    branch="$(git -C "$plugin_dir" symbolic-ref -q --short HEAD 2>/dev/null || true)"
    if [ -z "$branch" ]; then
      gum log --level warn "$name (detached HEAD; skipping)"
      continue
    fi

    dotfiles_run "  Pulling $name..." git -C "$plugin_dir" pull --ff-only \
      || gum log --level warn "$name pull failed; continuing"
  done
  shopt -u nullglob
}

sync_shell_completions() {
  gum log --level info "Syncing shell completions..."
  mkdir -p "$C"

  if command -v uvx &>/dev/null; then
    _LLM_COMPLETE=zsh_source uvx llm >"$C/_llm" 2>/dev/null \
      || gum log --level warn "llm completion generation failed"
  fi

  dotfiles_write_if_command bootdev "$C/_bootdev" bootdev completion zsh
  dotfiles_write_if_command ov      "$C/_ov"      ov --completion zsh
  dotfiles_write_if_command just    "$C/_just"    just --completions zsh
  dotfiles_write_if_command codex   "$C/_codex"   codex completion zsh
  dotfiles_write_if_command jj      "$C/_jj"      jj util completion zsh
  dotfiles_write_if_command linear  "$C/_linear"  linear completions zsh
  dotfiles_write_if_command sesh    "$C/_sesh"    sesh completion zsh
  dotfiles_write_if_command op      "$C/_op"      op completion zsh

  if command -v try-rs &>/dev/null; then
    cat >"$C/_try-rs" <<'TRYEOF'
# try-rs shell wrapper (cd into selected experiment)
try-rs() {
  for arg in "$@"; do
    case "$arg" in
      -*) command try-rs "$@"; return ;;
    esac
  done
  local output
  output=$(command try-rs "$@")
  if [[ -n "$output" ]]; then
    eval "$output"
  fi
}
alias try="try-rs"

# native zsh completion for try-rs
_try_rs_complete() {
  local tries_path="${TRY_PATH:-$HOME/work/tries}"
  local -a dirs=()
  local p
  for p in ${(s:,:)tries_path}; do
    [[ -d "$p" ]] && dirs+=("$p"/*(/N:t))
  done
  compadd -a dirs
}
compdef _try_rs_complete try-rs
compdef _try_rs_complete try
TRYEOF
  fi
}

sync_shell_functions() {
  gum log --level info "Syncing shell functions..."
  mkdir -p "$F"

  dotfiles_write_if_command starship "$F/_starship.zsh" starship init zsh
  dotfiles_write_if_command atuin    "$F/_atuin.zsh"    atuin init zsh --disable-up-arrow

  if command -v mise &>/dev/null; then
    # Cache full interactive mise activation for `.zshrc` to source quickly.
    # Non-interactive shells use mise shims from `.zshenv` instead.
    env -u __MISE_DIFF \
      -u __MISE_SESSION \
      -u __MISE_ORIG_PATH \
      -u MISE_SHELL \
      -u __MISE_ZSH_PRECMD_RUN \
      mise activate zsh >"$F/_mise.zsh" 2>/dev/null \
      || gum log --level warn "mise activation cache generation failed"
  fi
}

sync_bat_cache() {
  command -v bat &>/dev/null || return 0
  dotfiles_run "Building bat cache..." bat cache --build
}

sync_skillshare() {
  command -v skillshare &>/dev/null || return 0
  gum log --level info "Syncing Skillshare skills..."
  skillshare update --all
  skillshare sync
}

host_docs_dir() {
  local host
  host="$(hostname -s || true)"
  host="${host:-unknown-host}"
  host="${host//[^A-Za-z0-9._-]/-}"
  printf 'generated/docs/%s\n' "$host"
}

list_apps() {
  local dir="$1"
  find "$dir" -maxdepth 1 -name '*.app' -print 2>/dev/null \
    | sed -E 's|^.*/||; s|\.app$||' \
    | LC_ALL=en_US.UTF-8 sort
}

sync_host_inventory() {
  gum log --level info "Backing up installed packages..."

  local docs_dir
  docs_dir="$(host_docs_dir)"
  mkdir -p "$docs_dir"

  if command -v brew &>/dev/null; then
    brew bundle dump --file="$docs_dir/brew_dump.txt" --force \
      || gum log --level warn "brew bundle dump failed"
    brew leaves | LC_ALL=en_US.UTF-8 sort >"$docs_dir/brew_leaves.txt" \
      || gum log --level warn "brew leaves failed"
    brew list --installed-on-request | LC_ALL=en_US.UTF-8 sort >"$docs_dir/brew_installed.txt" \
      || gum log --level warn "brew list failed"
  fi

  if command -v gh &>/dev/null; then
    gh extension list | awk '{print $3}' | LC_ALL=en_US.UTF-8 sort >"$docs_dir/gh_extensions.txt" \
      || gum log --level warn "gh extension list failed"
  fi

  if [ -d "/Applications" ]; then
    list_apps /Applications >"$docs_dir/applications.txt" \
      || gum log --level warn "applications scan failed"
  fi

  if [ -d "/Applications/Setapp" ]; then
    list_apps /Applications/Setapp >"$docs_dir/setapp.txt" \
      || gum log --level warn "setapp scan failed"
  fi
}

sync_vendor_plugins
sync_shell_completions
sync_shell_functions
sync_bat_cache
rm -f ~/.zcompdump*
sync_skillshare
sync_host_inventory

gum log --level info "Sync done ✓"
