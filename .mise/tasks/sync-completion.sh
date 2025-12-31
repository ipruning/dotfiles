#!/usr/bin/env bash
#MISE description="Sync shell completion files"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

[ -d config/shell/completions ] || mkdir -p config/shell/completions

if command -v uvx >/dev/null 2>&1; then
  _LLM_COMPLETE=zsh_source uvx llm > config/shell/completions/_llm
fi

if command -v bootdev >/dev/null 2>&1; then
  bootdev completion zsh > config/shell/completions/_bootdev
fi

if command -v ov >/dev/null 2>&1; then
  ov --completion zsh > config/shell/completions/_ov
fi

if command -v just >/dev/null 2>&1; then
  just --completions zsh > config/shell/completions/_just
fi

if command -v codex >/dev/null 2>&1; then
  codex completion zsh > config/shell/completions/_codex
fi

if command -v jj >/dev/null 2>&1; then
  jj util completion zsh > config/shell/completions/_jj
fi

if command -v linear >/dev/null 2>&1; then
  linear completions zsh > config/shell/completions/_linear
fi

if command -v starship >/dev/null 2>&1; then
  starship init zsh > config/shell/functions/_starship.zsh
fi

if command -v atuin >/dev/null 2>&1; then
  atuin init zsh --disable-up-arrow > config/shell/functions/_atuin.zsh
fi

rm -f ~/.zcompdump*
