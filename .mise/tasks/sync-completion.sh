#!/usr/bin/env bash
#MISE description="Sync shell completion files"

set -euo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

[ -d config/shell/completions ] || mkdir -p config/shell/completions

if which uvx >/dev/null 2>&1; then
  _LLM_COMPLETE=zsh_source uvx llm > config/shell/completions/_llm
fi

if which bootdev >/dev/null 2>&1; then
  bootdev completion zsh > config/shell/completions/_bootdev
fi

if which ov >/dev/null 2>&1; then
  ov --completion zsh > config/shell/completions/_ov
fi

if which just >/dev/null 2>&1; then
  just --completions zsh > config/shell/completions/_just
fi

if which codex >/dev/null 2>&1; then
  codex completion zsh > config/shell/completions/_codex
fi

if which jj >/dev/null 2>&1; then
  jj util completion zsh > config/shell/completions/_jj
fi

if which linear >/dev/null 2>&1; then
  linear completions zsh > config/shell/completions/_linear
fi

rm -f ~/.zcompdump*
