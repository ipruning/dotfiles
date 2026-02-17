#!/usr/bin/env bash
#MISE description="Sync shell completion files"

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib.sh"

require_cmd git
REPO_ROOT="$(repo_root)"
cd "$REPO_ROOT"

printf "\033[34m==> Syncing Vendor Plugins (git pull)...\033[0m\n"

PLUGINS_DIR="$REPO_ROOT/generated/plugins"

if [ -d "$PLUGINS_DIR" ]; then
  shopt -s nullglob
  for plugin_dir in "$PLUGINS_DIR"/*; do
    [ -d "$plugin_dir" ] || continue

    if ! git -C "$plugin_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      continue
    fi

    plugin_name="$(basename "$plugin_dir")"

    if ! git -C "$plugin_dir" remote get-url origin >/dev/null 2>&1; then
      printf " - %s (no origin remote; skipping)\n" "$plugin_name"
      continue
    fi

    branch="$(git -C "$plugin_dir" symbolic-ref -q --short HEAD 2>/dev/null || true)"
    if [ -z "$branch" ]; then
      printf " - %s (detached HEAD; skipping)\n" "$plugin_name"
      continue
    fi

    printf " - %s (%s)\n" "$plugin_name" "$branch"
    if ! git -C "$plugin_dir" pull --ff-only; then
      printf "   -> pull failed; continuing\n"
    fi
  done
  shopt -u nullglob
else
  printf " - generated/plugins not found; skipping\n"
fi

printf "\033[34m==> Syncing Shell Completion...\033[0m\n"

GENERATED_COMPLETIONS_DIR="$REPO_ROOT/generated/completions"

[ -d "$GENERATED_COMPLETIONS_DIR" ] || mkdir -p "$GENERATED_COMPLETIONS_DIR"

if command -v uvx >/dev/null 2>&1; then
  _LLM_COMPLETE=zsh_source uvx llm > "$GENERATED_COMPLETIONS_DIR/_llm"
fi

if command -v bootdev >/dev/null 2>&1; then
  bootdev completion zsh > "$GENERATED_COMPLETIONS_DIR/_bootdev"
fi

if command -v ov >/dev/null 2>&1; then
  ov --completion zsh > "$GENERATED_COMPLETIONS_DIR/_ov"
fi

if command -v just >/dev/null 2>&1; then
  just --completions zsh > "$GENERATED_COMPLETIONS_DIR/_just"
fi

if command -v codex >/dev/null 2>&1; then
  codex completion zsh > "$GENERATED_COMPLETIONS_DIR/_codex"
fi

if command -v jj >/dev/null 2>&1; then
  jj util completion zsh > "$GENERATED_COMPLETIONS_DIR/_jj"
fi

if command -v linear >/dev/null 2>&1; then
  linear completions zsh > "$GENERATED_COMPLETIONS_DIR/_linear"
fi

printf "\033[34m==> Syncing Shell Functions...\033[0m\n"

GENERATED_FUNCTIONS_DIR="$REPO_ROOT/generated/functions"

[ -d "$GENERATED_FUNCTIONS_DIR" ] || mkdir -p "$GENERATED_FUNCTIONS_DIR"

if command -v starship >/dev/null 2>&1; then
  starship init zsh > "$GENERATED_FUNCTIONS_DIR/_starship.zsh"
fi

if command -v atuin >/dev/null 2>&1; then
  atuin init zsh --disable-up-arrow > "$GENERATED_FUNCTIONS_DIR/_atuin.zsh"
fi

if command -v mise >/dev/null 2>&1; then
  mise activate zsh > "$GENERATED_FUNCTIONS_DIR/_mise.zsh"
fi

if command -v sesh >/dev/null 2>&1; then
  sesh completion zsh > "$GENERATED_COMPLETIONS_DIR/_sesh"
fi

MODULES_DIR="$REPO_ROOT/modules"

if command -v op >/dev/null 2>&1; then
  op inject --in-file "$MODULES_DIR/zsh/env.private.tpl.zsh" --out-file "$MODULES_DIR/zsh/env.private.zsh"
fi

rm -f ~/.zcompdump*
