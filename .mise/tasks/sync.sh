#!/usr/bin/env bash
#MISE description="Sync shell completion files"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# -- Vendor plugins ------------------------------------------------------------

gum log --level info "Syncing vendor plugins (git pull)..."

if [ -d generated/plugins ]; then
  shopt -s nullglob
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

    if ! gum spin --title "  Pulling $name..." -- git -C "$plugin_dir" pull --ff-only; then
      gum log --level warn "$name pull failed; continuing"
    fi
  done
  shopt -u nullglob
else
  gum log --level warn "generated/plugins not found; skipping"
fi

# -- Shell completions ---------------------------------------------------------

gum log --level info "Syncing shell completions..."

mkdir -p generated/completions
C="generated/completions"

command -v uvx      &>/dev/null && { _LLM_COMPLETE=zsh_source uvx llm > "$C/_llm" 2>/dev/null || true; }
command -v bootdev  &>/dev/null && { bootdev completion zsh    > "$C/_bootdev" 2>/dev/null || true; }
command -v ov       &>/dev/null && { ov --completion zsh       > "$C/_ov"      2>/dev/null || true; }
command -v just     &>/dev/null && { just --completions zsh    > "$C/_just"    2>/dev/null || true; }
command -v codex    &>/dev/null && { codex completion zsh      > "$C/_codex"   2>/dev/null || true; }
command -v jj       &>/dev/null && { jj util completion zsh    > "$C/_jj"      2>/dev/null || true; }
command -v linear   &>/dev/null && { linear completions zsh    > "$C/_linear"  2>/dev/null || true; }
command -v sesh     &>/dev/null && { sesh completion zsh       > "$C/_sesh"    2>/dev/null || true; }
command -v op       &>/dev/null && { op completion zsh         > "$C/_op"      2>/dev/null || true; }

if command -v try-rs &>/dev/null; then
  cat > "$C/_try-rs" <<'TRYEOF'
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

# -- Shell functions -----------------------------------------------------------

gum log --level info "Syncing shell functions..."

mkdir -p generated/functions
F="generated/functions"

command -v starship &>/dev/null && { starship init zsh > "$F/_starship.zsh" 2>/dev/null || true; }
command -v atuin    &>/dev/null && { atuin init zsh --disable-up-arrow > "$F/_atuin.zsh" 2>/dev/null || true; }

if command -v mise &>/dev/null; then
  env -u __MISE_DIFF \
    -u __MISE_SESSION \
    -u __MISE_ORIG_PATH \
    -u MISE_SHELL \
    -u __MISE_ZSH_PRECMD_RUN \
    mise activate zsh > "$F/_mise.zsh" 2>/dev/null || true
fi

# -- Bat cache -----------------------------------------------------------------

command -v bat &>/dev/null && { gum spin --title "Building bat cache..." -- bat cache --build; }

rm -f ~/.zcompdump*
