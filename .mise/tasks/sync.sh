#!/usr/bin/env bash
#MISE description="Sync shell completion files"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

printf "\033[34m==> Syncing Shell Completion...\033[0m\n"

GENERATED_COMPLETIONS_DIR="$HOME/dotfiles/generated/completions"

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

GENERATED_FUNCTIONS_DIR="$HOME/dotfiles/generated/functions"

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

rm -f ~/.zcompdump*
